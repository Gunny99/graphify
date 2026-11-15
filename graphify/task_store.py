"""SQLite-backed durable task queue for independent Graphify agents.

The store is provider-neutral. Agents are expected to access it through the
Graphify MCP server, not by opening the database file directly.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

AGENT_HEARTBEAT_TTL_SECONDS = 120


from graphify.orchestration import (
    OrchestrationValidationError,
    estimate_end_to_end_cost,
    rank_qualified_agents,
    result_meets_quality_gate,
    validate_agent_profile,
    validate_result_envelope,
    validate_review_envelope,
    validate_execution_plan,
    validate_run_envelope,
    validate_task_envelope,
    validate_task_graph,
)


class TaskStoreError(RuntimeError):
    """Base exception for durable task-store failures."""


class TaskNotFoundError(TaskStoreError):
    """A requested run, task, result, or agent does not exist."""


class TaskLeaseError(TaskStoreError):
    """A lease is absent, expired, or owned by another agent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise OrchestrationValidationError(f"value is not JSON serializable: {exc}") from exc


def _required_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskStoreError(f"{path} must be a non-empty string")
    return value


def _decode(value: str) -> dict[str, Any]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TaskStoreError(f"stored JSON is corrupt: {exc}") from exc
    if not isinstance(loaded, dict):
        raise TaskStoreError("stored orchestration record is not a JSON object")
    return loaded


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expired(stamp: str | None, now: datetime) -> bool:
    if not stamp:
        return False
    deadline = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return deadline <= now


class TaskStore:
    """Transactional run/task/agent/result store using SQLite WAL mode."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0):
        self.path = Path(path)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(f"PRAGMA busy_timeout = {int(self.timeout_seconds * 1000)}")
        return con

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _initialize(self) -> None:
        con = self._connect()
        try:
            con.execute("PRAGMA journal_mode = WAL")
            con.execute("PRAGMA synchronous = NORMAL")
            version = int(con.execute("PRAGMA user_version").fetchone()[0])
            if version > 1:
                raise TaskStoreError(
                    f"task database schema {version} is newer than this Graphify version"
                )
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                    task_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_token_hash TEXT,
                    lease_expires_at REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_ready
                    ON tasks(status, priority DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_tasks_run
                    ON tasks(run_id, status);
                CREATE INDEX IF NOT EXISTS idx_tasks_lease
                    ON tasks(lease_owner, status, lease_expires_at);

                CREATE TABLE IF NOT EXISTS results (
                    result_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    attempt INTEGER NOT NULL,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, attempt)
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    result_id TEXT NOT NULL REFERENCES results(result_id) ON DELETE CASCADE,
                    reviewer_agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                    review_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    task_id TEXT,
                    agent_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            con.execute("PRAGMA user_version = 1")
        finally:
            con.close()

    @staticmethod
    def _event(
        con: sqlite3.Connection,
        *,
        run_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        task_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        con.execute(
            """
            INSERT INTO events(run_id, task_id, agent_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, task_id, agent_id, event_type, _json(payload), _utc_now()),
        )

    @staticmethod
    def _set_task(
        con: sqlite3.Connection,
        row: sqlite3.Row,
        task: dict[str, Any],
        status: str,
        *,
        lease_owner: str | None = None,
        lease_token_hash: str | None = None,
        lease_expires_at: float | None = None,
        attempt: int | None = None,
    ) -> None:
        now = _utc_now()
        task["status"] = status
        task["updated_at"] = now
        if attempt is not None:
            task["attempt"] = attempt
        if status != "leased":
            task.pop("lease_expires_at", None)
        if status not in {"leased", "submitted", "needs_review", "queued"}:
            task.pop("estimated_cost_reserved", None)
        con.execute(
            """
            UPDATE tasks
            SET task_json=?, status=?, attempt=?, lease_owner=?,
                lease_token_hash=?, lease_expires_at=?, updated_at=?
            WHERE task_id=?
            """,
            (
                _json(task),
                status,
                task["attempt"],
                lease_owner,
                lease_token_hash,
                lease_expires_at,
                now,
                row["task_id"],
            ),
        )

    def _mark_verification_parent_needs_review(
        self,
        con: sqlite3.Connection,
        verification_task: Mapping[str, Any],
        reason: str,
    ) -> None:
        """Keep an unverified source result provisional when verification ends."""
        parent_task_id = verification_task.get("parent_task_id")
        if not isinstance(parent_task_id, str) or not parent_task_id:
            return
        parent_row = con.execute(
            "SELECT * FROM tasks WHERE task_id=?", (parent_task_id,)
        ).fetchone()
        if parent_row is None or parent_row["status"] not in {"submitted", "needs_review"}:
            return
        parent_task = _decode(parent_row["task_json"])
        parent_task["verification_failure"] = {
            "verification_task_id": verification_task.get("task_id"),
            "reason": reason,
        }
        self._set_task(con, parent_row, parent_task, "needs_review")
        self._event(
            con,
            run_id=parent_row["run_id"],
            task_id=parent_task_id,
            event_type="verification_unavailable",
            payload={
                "verification_task_id": verification_task.get("task_id"),
                "reason": reason,
            },
        )

    def _refresh_run_status(self, con: sqlite3.Connection, run_id: str) -> str:
        row = con.execute(
            "SELECT run_json FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise TaskNotFoundError(f"run not found: {run_id}")
        run = _decode(row["run_json"])
        if run["status"] == "cancelled":
            return "cancelled"
        actual_cost = self._get_actual_cost(con, run_id)
        reserved_cost = self._get_reserved_cost(con, run_id)
        max_total = float(run["cost_policy"]["max_total"])
        task_rows = con.execute(
            "SELECT task_id, task_json, status FROM tasks WHERE run_id=?", (run_id,)
        ).fetchall()
        statuses = [item["status"] for item in task_rows]
        status_by_task = {item["task_id"]: item["status"] for item in task_rows}
        has_terminal_work_failure = any(
            item["status"] in {"failed", "rejected", "blocked"}
            and _decode(item["task_json"]).get("task_type") != "verification"
            for item in task_rows
        )
        has_runnable_queued = any(
            item["status"] == "queued"
            and all(
                status_by_task.get(dependency) == "accepted"
                for dependency in _decode(item["task_json"]).get("depends_on", [])
            )
            for item in task_rows
        )
        if actual_cost + reserved_cost > max_total:
            status = "failed"
            run["failure_reason"] = "run_cost_budget_exceeded"
        elif statuses and all(status == "accepted" for status in statuses):
            status = "accepted"
        elif any(item == "leased" for item in statuses):
            status = "running"
        elif has_runnable_queued:
            # Keep eligible independent branches running while unresolved
            # dependencies remain visible as submitted/needs_review.
            status = "queued"
        elif any(status == "submitted" for status in statuses):
            status = "awaiting_review"
        elif has_terminal_work_failure:
            # A terminally failed branch makes full run acceptance impossible.
            # Keep active/runnable work ahead of this check, but do not let an
            # unrelated needs_review branch mask an unrecoverable work failure.
            status = "failed"
        elif any(status == "needs_review" for status in statuses):
            status = "provisional"
        elif any(status in {"failed", "rejected", "blocked"} for status in statuses):
            # A failed verification task is reflected as needs_review on its
            # parent; absent that parent state, keep the run conservatively failed.
            status = "failed"
        elif statuses and all(status == "cancelled" for status in statuses):
            status = "cancelled"
        else:
            status = "failed"
        run["status"] = status
        run["updated_at"] = _utc_now()
        con.execute(
            "UPDATE runs SET status=?, run_json=?, updated_at=? WHERE run_id=?",
            (status, _json(run), run["updated_at"], run_id),
        )
        return status

    def _reap_expired_leases(self, con: sqlite3.Connection, now_epoch: float) -> None:
        rows = con.execute(
            """
            SELECT task_id, run_id, task_json, attempt, max_attempts, lease_owner,
                   lease_expires_at
            FROM tasks
            WHERE status='leased'
            """
        ).fetchall()
        now_dt = datetime.fromtimestamp(now_epoch, timezone.utc)
        changed_runs: set[str] = set()
        for row in rows:
            task = _decode(row["task_json"])
            deadline_expired = _expired(task.get("deadline_at"), now_dt)
            lease_expired = (
                row["lease_expires_at"] is None
                or float(row["lease_expires_at"]) <= now_epoch
            )
            if not deadline_expired and not lease_expired:
                continue
            attempt = int(row["attempt"])
            status = (
                "failed"
                if deadline_expired or attempt >= int(row["max_attempts"])
                else "queued"
            )
            if row["lease_owner"] and status == "queued":
                failed_agents = set(task["input"].get("failed_agent_ids", []))
                failed_agents.add(str(row["lease_owner"]))
                task["input"]["failed_agent_ids"] = sorted(failed_agents)
            # No usage telemetry is available for an expired lease. Move the
            # old attempt's estimate into a durable uncertainty reserve so a
            # later claim cannot overwrite it with the next attempt's estimate.
            unreported_reserve = float(task.pop("estimated_cost_reserved", 0.0))
            if unreported_reserve > 0:
                task["unreported_cost_reserved"] = (
                    float(task.get("unreported_cost_reserved", 0.0))
                    + unreported_reserve
                )
            self._set_task(con, row, task, status)
            if status == "failed" and task.get("task_type") == "verification":
                reason = (
                    "verification task deadline expired"
                    if deadline_expired
                    else "verification lease expired after all attempts"
                )
                self._mark_verification_parent_needs_review(con, task, reason)
            self._event(
                con,
                run_id=row["run_id"],
                task_id=row["task_id"],
                event_type="deadline_expired" if deadline_expired else "lease_expired",
                payload={
                    "attempt": attempt,
                    "new_status": status,
                    **({"deadline_at": task.get("deadline_at")} if deadline_expired else {}),
                },
            )
            changed_runs.add(row["run_id"])
        for run_id in changed_runs:
            self._refresh_run_status(con, run_id)

    def register_agent(
        self,
        value: Mapping[str, Any],
        *,
        trusted_profile: bool = False,
    ) -> dict[str, Any]:
        """Register a profile from a trusted local operator, never an agent self-assertion."""
        if not trusted_profile:
            raise TaskStoreError(
                "agent registration with pricing and quality profiles requires a trusted local operator"
            )
        profile = dict(validate_agent_profile(value))
        agent_id = str(profile["agent_id"])
        auth_token = profile.pop("auth_token", None)
        if not isinstance(auth_token, str) or len(auth_token) < 24:
            raise TaskStoreError("trusted agent registration requires an auth_token of at least 24 characters")
        profile["_auth_token_hash"] = _token_hash(auth_token)
        now = _utc_now()
        with self._transaction() as con:
            active = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                (agent_id,),
            ).fetchone()[0]
            pending_results = con.execute(
                """
                SELECT t.task_json, r.result_id
                FROM tasks t JOIN results r ON r.task_id=t.task_id
                WHERE r.agent_id=? AND t.status IN ('submitted', 'needs_review')
                """,
                (agent_id,),
            ).fetchall()
            awaiting_review = any(
                _decode(row["task_json"]).get("result_id") == row["result_id"]
                for row in pending_results
            )
            existing = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if existing and (active or awaiting_review):
                previous = _decode(existing["profile_json"])
                immutable_keys = (
                    "provider", "model", "model_version", "cost_profile",
                    "quality_profiles", "_auth_token_hash",
                )
                if any(previous[key] != profile[key] for key in immutable_keys):
                    raise TaskStoreError(
                        "cannot change model identity, pricing, or quality profile while this agent owns leases or has pending verification results"
                    )
            registered_at = (
                _decode(existing["profile_json"]).get("registered_at") if existing else None
            ) or profile.get("registered_at") or now
            saved = dict(profile)
            saved["registered_at"] = registered_at
            saved["updated_at"] = now
            con.execute(
                """
                INSERT INTO agents(agent_id, profile_json, status, registered_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    profile_json=excluded.profile_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (agent_id, _json(saved), saved["status"], registered_at, now),
            )
            return saved

    def authenticate_agent(self, agent_id: str, auth_token: str) -> dict[str, Any]:
        """Authenticate an MCP client against a locally registered agent token."""
        agent_id = _required_string(agent_id, "agent_id")
        auth_token = _required_string(auth_token, "agent_token")
        with self._transaction() as con:
            row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if row is None:
                raise TaskLeaseError("agent authentication failed")
            profile = _decode(row["profile_json"])
            stored = str(profile.get("_auth_token_hash") or "")
            supplied = _token_hash(auth_token)
            if not stored or not secrets.compare_digest(stored, supplied):
                raise TaskLeaseError("agent authentication failed")
            con.execute("UPDATE agents SET updated_at=? WHERE agent_id=?", (_utc_now(), agent_id))
            return {
                "agent_id": profile["agent_id"],
                "provider": profile["provider"],
                "model": profile["model"],
                "model_version": profile["model_version"],
                "status": profile["status"],
            }

    def list_agents(self) -> list[dict[str, Any]]:
        """Return registered agent identities and capability labels, never token hashes."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT profile_json FROM agents ORDER BY agent_id"
            ).fetchall()
        result = []
        for row in rows:
            profile = _decode(row["profile_json"])
            result.append({
                "agent_id": profile["agent_id"],
                "provider": profile["provider"],
                "model": profile["model"],
                "model_version": profile["model_version"],
                "capabilities": profile["capabilities"],
                "status": profile["status"],
                "quality_profiles": profile["quality_profiles"],
            })
        return result

    def create_run(
        self,
        run_value: Mapping[str, Any],
        task_values: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Atomically create a run and its validated, acyclic task graph."""
        run = validate_run_envelope(run_value)
        tasks = [validate_task_envelope(item) for item in task_values]
        if not tasks:
            raise OrchestrationValidationError("a run must contain at least one task")
        validate_task_graph(tasks)
        validate_execution_plan(run, tasks)
        run_id = str(run["run_id"])
        if run["status"] != "queued":
            raise OrchestrationValidationError("new runs must start with status='queued'")
        for task in tasks:
            if task["run_id"] != run_id:
                raise OrchestrationValidationError("every task must reference the new run_id")
            if task["status"] != "queued" or task["attempt"] != 0:
                raise OrchestrationValidationError("new tasks must start queued with attempt=0")
        with self._transaction() as con:
            if con.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
                raise TaskStoreError(f"run already exists: {run_id}")
            run_copy = dict(run)
            now = _utc_now()
            run_copy["created_at"] = run_copy.get("created_at") or now
            run_copy["updated_at"] = now
            con.execute(
                "INSERT INTO runs(run_id, status, run_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, "queued", _json(run_copy), run_copy["created_at"], now),
            )
            for task in tasks:
                task_copy = dict(task)
                priority = task_copy.get("priority", 0)
                if not isinstance(priority, int) or isinstance(priority, bool):
                    raise OrchestrationValidationError("task.priority must be an integer")
                task_copy["created_at"] = task_copy.get("created_at") or now
                task_copy["updated_at"] = now
                con.execute(
                    """
                    INSERT INTO tasks(task_id, run_id, task_json, status, attempt,
                                      max_attempts, priority, created_at, updated_at)
                    VALUES (?, ?, ?, 'queued', 0, ?, ?, ?, ?)
                    """,
                    (
                        task_copy["task_id"],
                        run_id,
                        _json(task_copy),
                        task_copy["max_attempts"],
                        priority,
                        task_copy["created_at"],
                        now,
                    ),
                )
                self._event(
                    con, run_id=run_id, task_id=task_copy["task_id"],
                    event_type="task_created", payload={"task_type": task_copy["task_type"]},
                )
            self._event(con, run_id=run_id, event_type="run_created", payload={"task_count": len(tasks)})
        return self.get_run_status(run_id)

    @staticmethod
    def _generation_cost(profile: Mapping[str, Any], usage: Mapping[str, Any]) -> float:
        """Price token usage from the trusted registered model profile, not agent claims."""
        input_tokens = int(usage["input_tokens"])
        cached_tokens = int(usage["cached_input_tokens"])
        output_tokens = int(usage["output_tokens"])
        if cached_tokens > input_tokens:
            raise TaskStoreError("cached_input_tokens cannot exceed input_tokens")
        uncached_tokens = input_tokens - cached_tokens
        cost = (
            uncached_tokens * float(profile["input_cost_per_million_tokens"])
            + cached_tokens * float(profile["cached_input_cost_per_million_tokens"])
            + output_tokens * float(profile["output_cost_per_million_tokens"])
        ) / 1_000_000
        if not math.isfinite(cost) or cost < 0:
            raise TaskStoreError("trusted pricing profile produced an invalid cost")
        return cost

    def _get_reserved_cost(self, con: sqlite3.Connection, run_id: str) -> float:
        """Sum active estimates and durable reserves for attempts without usage telemetry."""
        total = 0.0
        rows = con.execute(
            "SELECT status, task_json FROM tasks WHERE run_id=?",
            (run_id,),
        ).fetchall()
        active_statuses = {"leased", "submitted", "needs_review", "queued"}
        for row in rows:
            task = _decode(row["task_json"])
            total += float(task.get("unreported_cost_reserved", 0.0))
            if row["status"] in active_statuses:
                total += float(task.get("estimated_cost_reserved", 0.0))
        return total

    def _get_actual_cost(self, con: sqlite3.Connection, run_id: str) -> float:
        total = 0.0
        result_rows = con.execute(
            """
            SELECT r.result_json FROM results r
            JOIN tasks t ON t.task_id=r.task_id
            WHERE t.run_id=?
            """,
            (run_id,),
        ).fetchall()
        for row in result_rows:
            total += float(_decode(row["result_json"])["usage"]["direct_cost"])
        review_rows = con.execute(
            """
            SELECT rv.review_json FROM reviews rv
            JOIN results rs ON rs.result_id=rv.result_id
            JOIN tasks t ON t.task_id=rs.task_id
            WHERE t.run_id=?
            """,
            (run_id,),
        ).fetchall()
        for row in review_rows:
            total += float(_decode(row["review_json"])["usage"]["direct_cost"])
        return total

    def _get_task_actual_cost(self, con: sqlite3.Connection, task_id: str) -> float:
        """Sum actual costs attributable to one logical task or verifier attempt."""
        task_row = con.execute(
            "SELECT task_json FROM tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
        task = _decode(task_row["task_json"]) if task_row else {}
        total = 0.0
        if task.get("task_type") == "verification":
            result_id = task.get("input", {}).get("result_id")
            if not result_id:
                return 0.0
            rows = con.execute(
                "SELECT review_json FROM reviews WHERE result_id=?",
                (result_id,),
            ).fetchall()
            for row in rows:
                total += float(_decode(row["review_json"])["usage"]["direct_cost"])
            return total

        result_rows = con.execute(
            "SELECT result_json FROM results WHERE task_id=?",
            (task_id,),
        ).fetchall()
        for row in result_rows:
            total += float(_decode(row["result_json"])["usage"]["direct_cost"])
        review_rows = con.execute(
            """
            SELECT rv.review_json
            FROM reviews rv
            JOIN results rs ON rs.result_id=rv.result_id
            WHERE rs.task_id=?
            """,
            (task_id,),
        ).fetchall()
        for row in review_rows:
            total += float(_decode(row["review_json"])["usage"]["direct_cost"])
        return total

    def claim_task(self, agent_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        """Claim the cheapest eligible task lease for this agent, atomically."""
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be an integer between 30 and 3600")
        token = secrets.token_urlsafe(32)
        now_epoch = time.time()
        expires_epoch = now_epoch + lease_seconds
        expires_at = datetime.fromtimestamp(expires_epoch, timezone.utc).isoformat()
        now_dt = datetime.fromtimestamp(now_epoch, timezone.utc)
        with self._transaction() as con:
            self._reap_expired_leases(con, now_epoch)
            # Sweep every expired queued task before agent eligibility or
            # concurrency checks; otherwise an inactive/full/incompatible
            # agent could leave expired work queued indefinitely.
            queued_rows = con.execute(
                "SELECT * FROM tasks WHERE status='queued'"
            ).fetchall()
            expired_runs: set[str] = set()
            for queued_row in queued_rows:
                queued_task = _decode(queued_row["task_json"])
                if not _expired(queued_task.get("deadline_at"), now_dt):
                    continue
                self._set_task(con, queued_row, queued_task, "failed")
                if queued_task.get("task_type") == "verification":
                    self._mark_verification_parent_needs_review(
                        con, queued_task, "verification task deadline expired before claim"
                    )
                self._event(
                    con,
                    run_id=queued_row["run_id"],
                    task_id=queued_row["task_id"],
                    event_type="deadline_expired",
                    payload={"deadline_at": queued_task.get("deadline_at")},
                )
                expired_runs.add(queued_row["run_id"])
            for expired_run_id in expired_runs:
                self._refresh_run_status(con, expired_run_id)
            agent_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent_row is None:
                raise TaskNotFoundError(f"agent not registered: {agent_id}")
            agent = validate_agent_profile(_decode(agent_row["profile_json"]))
            if agent["status"] != "active":
                return None
            con.execute("UPDATE agents SET updated_at=? WHERE agent_id=?", (_utc_now(), agent_id))
            fresh_after = datetime.fromtimestamp(
                now_epoch - AGENT_HEARTBEAT_TTL_SECONDS, timezone.utc
            ).isoformat()
            active_count = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                (agent_id,),
            ).fetchone()[0]
            if active_count >= agent["max_concurrency"]:
                return None

            rows = con.execute(
                "SELECT * FROM tasks WHERE status='queued' ORDER BY priority DESC, created_at ASC"
            ).fetchall()
            for row in rows:
                task = _decode(row["task_json"])
                if not set(task["required_capabilities"]).issubset(set(agent["capabilities"])):
                    continue

                dep_rows = {
                    dep["task_id"]: dep["status"]
                    for dep in con.execute(
                        "SELECT task_id, status FROM tasks WHERE run_id=?",
                        (row["run_id"],),
                    )
                }
                dependency_statuses = [dep_rows.get(dep) for dep in task["depends_on"]]
                if any(status in {"failed", "rejected", "blocked", "cancelled"} for status in dependency_statuses):
                    self._set_task(con, row, task, "blocked")
                    self._event(
                        con, run_id=row["run_id"], task_id=row["task_id"],
                        event_type="dependency_blocked", payload={"depends_on": task["depends_on"]},
                    )
                    self._refresh_run_status(con, row["run_id"])
                    continue
                if any(status != "accepted" for status in dependency_statuses):
                    continue

                run_row = con.execute(
                    "SELECT run_json FROM runs WHERE run_id=?", (row["run_id"],)
                ).fetchone()
                if run_row is None:
                    raise TaskNotFoundError(f"run not found: {row['run_id']}")
                run = _decode(run_row["run_json"])
                if run["status"] in {"failed", "cancelled", "accepted"}:
                    continue
                execution = run["execution_policy"]
                active_in_run = con.execute(
                    "SELECT COUNT(*) FROM tasks WHERE run_id=? AND status='leased'",
                    (row["run_id"],),
                ).fetchone()[0]
                if active_in_run >= int(execution["max_parallel_agents"]):
                    continue
                if execution["strategy"] in {"single_agent", "single_with_review"}:
                    primary_agent_id = run.get("primary_agent_id")
                    if task["task_type"] != "verification" and primary_agent_id not in {None, agent_id}:
                        continue
                if task["input"].get("read_only") is True and "read_only" not in agent["capabilities"]:
                    continue
                task_scopes = set(task["data_scopes"])
                agent_scopes = set(agent["allowed_data_scopes"])
                if "*" not in agent_scopes and not task_scopes.issubset(agent_scopes):
                    continue
                excluded = set(task["input"].get("excluded_agent_ids", []))
                failed_agents = set(task["input"].get("failed_agent_ids", []))
                if agent_id in excluded:
                    continue
                if task["task_type"] == "verification" and "verify" not in agent["capabilities"]:
                    continue

                # Re-rank currently available agents so polling order cannot make
                # a more expensive qualified model steal work from a cheaper one.
                available_agents: list[dict[str, Any]] = []
                previously_failed_agents: list[dict[str, Any]] = []
                agent_rows = con.execute(
                    "SELECT agent_id, profile_json FROM agents "
                    "WHERE status='active' AND updated_at >= ?",
                    (fresh_after,),
                ).fetchall()
                for other_row in agent_rows:
                    other = validate_agent_profile(_decode(other_row["profile_json"]))
                    if not set(task["required_capabilities"]).issubset(set(other["capabilities"])):
                        continue
                    other_scopes = set(other["allowed_data_scopes"])
                    if "*" not in other_scopes and not task_scopes.issubset(other_scopes):
                        continue
                    if (
                        execution["strategy"] in {"single_agent", "single_with_review"}
                        and task["task_type"] != "verification"
                        and run.get("primary_agent_id") is not None
                        and other["agent_id"] != run["primary_agent_id"]
                    ):
                        continue
                    if other["agent_id"] in excluded:
                        continue
                    if task["task_type"] == "verification" and "verify" not in other["capabilities"]:
                        continue
                    if task["input"].get("read_only") is True and "read_only" not in other["capabilities"]:
                        continue
                    leased = con.execute(
                        "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                        (other["agent_id"],),
                    ).fetchone()[0]
                    if leased < other["max_concurrency"]:
                        if other["agent_id"] in failed_agents:
                            previously_failed_agents.append(other)
                        else:
                            available_agents.append(other)
                ranked = rank_qualified_agents(
                    available_agents,
                    role=task["role"],
                    domain=task["domain"],
                    currency=run["cost_policy"]["currency"],
                    estimated_input_tokens=task["input"].get("estimated_input_tokens", 0),
                    estimated_output_tokens=task["input"].get("estimated_output_tokens", 0),
                    estimated_cached_input_tokens=task["input"].get("estimated_cached_input_tokens", 0),
                    accuracy_target=run["quality_policy"]["accuracy_target"],
                    hallucination_max=run["quality_policy"]["hallucination_max"],
                )
                if not ranked and previously_failed_agents:
                    ranked = rank_qualified_agents(
                        available_agents + previously_failed_agents,
                        role=task["role"],
                        domain=task["domain"],
                        currency=run["cost_policy"]["currency"],
                        estimated_input_tokens=task["input"].get("estimated_input_tokens", 0),
                        estimated_output_tokens=task["input"].get("estimated_output_tokens", 0),
                        estimated_cached_input_tokens=task["input"].get("estimated_cached_input_tokens", 0),
                        accuracy_target=run["quality_policy"]["accuracy_target"],
                        hallucination_max=run["quality_policy"]["hallucination_max"],
                    )
                if not ranked or ranked[0]["agent_id"] != agent_id:
                    continue

                spent = self._get_actual_cost(con, row["run_id"])
                reserved = self._get_reserved_cost(con, row["run_id"])
                own_estimate = float(task.get("estimated_cost_reserved", 0.0))
                own_unreported = float(task.get("unreported_cost_reserved", 0.0))
                reserved_other = max(0.0, reserved - own_estimate - own_unreported)
                max_total = float(run["cost_policy"]["max_total"])
                expected = float(ranked[0]["estimated_total_cost"])
                if spent + own_unreported + expected > max_total:
                    task["last_failure"] = "run_cost_budget_exceeded"
                    task.pop("estimated_cost_reserved", None)
                    self._set_task(con, row, task, "failed")
                    self._event(
                        con, run_id=row["run_id"], task_id=row["task_id"],
                        event_type="task_budget_exceeded",
                        payload={
                            "reason": task["last_failure"],
                            "expected_cost": expected,
                            "spent": spent,
                            "unreported_cost_reserved": own_unreported,
                        },
                    )
                    self._refresh_run_status(con, row["run_id"])
                    continue
                if spent + own_unreported + reserved_other + expected > max_total:
                    # Another task's active estimate may be released; keep this task queued.
                    continue
                if task.get("cost_budget"):
                    task_budget = task["cost_budget"]
                    if task_budget["currency"] != run["cost_policy"]["currency"]:
                        task["last_failure"] = "task_cost_budget_currency_mismatch"
                    elif (
                        self._get_task_actual_cost(con, row["task_id"])
                        + own_unreported
                        + expected
                        > float(task_budget["max_total"])
                    ):
                        task["last_failure"] = "task_cost_budget_exceeded"
                    else:
                        task.pop("last_failure", None)
                    if task.get("last_failure"):
                        self._set_task(con, row, task, "failed")
                        self._event(
                            con, run_id=row["run_id"], task_id=row["task_id"],
                            event_type="task_budget_exceeded",
                            payload={"reason": task["last_failure"], "expected_cost": expected},
                        )
                        self._refresh_run_status(con, row["run_id"])
                        continue

                next_attempt = int(row["attempt"]) + 1
                task["attempt"] = next_attempt
                task["lease_expires_at"] = expires_at
                task["estimated_cost_reserved"] = expected
                self._set_task(
                    con,
                    row,
                    task,
                    "leased",
                    lease_owner=agent_id,
                    lease_token_hash=_token_hash(token),
                    lease_expires_at=expires_epoch,
                    attempt=next_attempt,
                )
                if (
                    execution["strategy"] in {"single_agent", "single_with_review"}
                    and task["task_type"] != "verification"
                    and run.get("primary_agent_id") is None
                ):
                    run["primary_agent_id"] = agent_id
                    run["updated_at"] = _utc_now()
                    con.execute(
                        "UPDATE runs SET run_json=?, updated_at=? WHERE run_id=?",
                        (_json(run), run["updated_at"], row["run_id"]),
                    )
                self._refresh_run_status(con, row["run_id"])
                self._event(
                    con,
                    run_id=row["run_id"],
                    task_id=row["task_id"],
                    agent_id=agent_id,
                    event_type="task_claimed",
                    payload={
                        "attempt": next_attempt,
                        "lease_expires_at": expires_at,
                        "estimated_total_cost": expected,
                        "currency": run["cost_policy"]["currency"],
                    },
                )
                claimed = dict(task)
                claimed["lease_token"] = token
                claimed["lease_expires_at"] = expires_at
                return claimed
        return None

    def _owned_lease(
        self,
        con: sqlite3.Connection,
        task_id: str,
        agent_id: str,
        lease_token: str,
    ) -> sqlite3.Row:
        row = con.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFoundError(f"task not found: {task_id}")
        if row["status"] != "leased" or row["lease_owner"] != agent_id:
            raise TaskLeaseError("task is not leased to this agent")
        if row["lease_expires_at"] is None or float(row["lease_expires_at"]) <= time.time():
            raise TaskLeaseError("task lease has expired")
        task = _decode(row["task_json"])
        if _expired(task.get("deadline_at"), datetime.now(timezone.utc)):
            raise TaskLeaseError("task deadline has expired")
        supplied_hash = _token_hash(_required_string(lease_token, "lease_token"))
        stored_hash = str(row["lease_token_hash"] or "")
        if not secrets.compare_digest(supplied_hash, stored_hash):
            raise TaskLeaseError("invalid lease token")
        return row

    def heartbeat_task(
        self,
        task_id: str,
        agent_id: str,
        lease_token: str,
        *,
        lease_seconds: int = 300,
    ) -> str:
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be an integer between 30 and 3600")
        with self._transaction() as con:
            row = self._owned_lease(con, task_id, agent_id, lease_token)
            task = _decode(row["task_json"])
            expires = datetime.now(timezone.utc).timestamp() + lease_seconds
            expires_at = datetime.fromtimestamp(expires, timezone.utc).isoformat()
            task["lease_expires_at"] = expires_at
            self._set_task(
                con,
                row,
                task,
                "leased",
                lease_owner=agent_id,
                lease_token_hash=row["lease_token_hash"],
                lease_expires_at=expires,
            )
            self._event(
                con,
                run_id=row["run_id"],
                task_id=task_id,
                agent_id=agent_id,
                event_type="lease_renewed",
                payload={"lease_expires_at": expires_at},
            )
            return expires_at

    def _create_verification_task(
        self,
        con: sqlite3.Connection,
        *,
        run_id: str,
        producer_task: Mapping[str, Any],
        result: Mapping[str, Any],
        reserved_cost: float,
    ) -> str:
        """Create a verifier-only task bound to one immutable result."""
        verification_id = f"verification::{result['result_id']}"
        existing = con.execute(
            "SELECT 1 FROM tasks WHERE task_id=?", (verification_id,)
        ).fetchone()
        if existing:
            # Never adopt a caller-created task as a verifier task. Task IDs are
            # globally unique, and a crafted collision could otherwise point a
            # submitted result at an unrelated task in this or another run.
            raise TaskStoreError(
                f"verification task ID collision: {verification_id}"
            )
        run_row = con.execute(
            "SELECT run_json FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run_row is None:
            raise TaskNotFoundError(f"run not found: {run_id}")
        run = _decode(run_row["run_json"])
        now = _utc_now()
        input_tokens = (
            int(result["usage"]["input_tokens"])
            + int(result["usage"]["output_tokens"])
        )
        verification_task = {
            "schema_version": 1,
            "task_id": verification_id,
            "run_id": run_id,
            "parent_task_id": producer_task["task_id"],
            "deadline_at": producer_task.get("deadline_at"),
            "data_scopes": list(producer_task["data_scopes"]),
            "task_type": "verification",
            "role": "verifier",
            "domain": producer_task["domain"],
            "objective": "Independently verify every material factual claim and its cited evidence.",
            "input": {
                "result_id": result["result_id"],
                "estimated_input_tokens": max(1, input_tokens),
                "estimated_output_tokens": 500,
                "estimated_cached_input_tokens": 0,
                "excluded_agent_ids": [str(result["agent"]["agent_id"])],
            },
            "context_refs": [{"source_type": "result", "result_id": result["result_id"]}],
            "depends_on": [],
            "required_capabilities": ["verify"],
            "output_schema": {"type": "review"},
            "acceptance_criteria": [
                "Every material factual/inference claim has a verdict",
                "Every supported claim has independent source evidence",
            ],
            "cost_budget": {
                "currency": run["cost_policy"]["currency"],
                "max_total": run["cost_policy"]["max_total"],
            },
            "attempt": 0,
            "max_attempts": 2,
            "priority": int(producer_task.get("priority", 0)),
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "estimated_cost_reserved": max(0.0, float(reserved_cost)),
        }
        validate_task_envelope(verification_task)
        con.execute(
            """
            INSERT INTO tasks(task_id, run_id, task_json, status, attempt,
                              max_attempts, priority, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', 0, ?, ?, ?, ?)
            """,
            (
                verification_id,
                run_id,
                _json(verification_task),
                verification_task["max_attempts"],
                verification_task["priority"],
                now,
                now,
            ),
        )
        self._event(
            con,
            run_id=run_id,
            task_id=verification_id,
            event_type="verification_task_created",
            payload={"result_id": result["result_id"], "reserved_cost": verification_task["estimated_cost_reserved"]},
        )
        return verification_id

    def submit_result(self, value: Mapping[str, Any], lease_token: str) -> dict[str, Any]:
        """Persist a result for the currently leased attempt; retries are idempotent."""
        result = validate_result_envelope(value)
        result_id = str(result["result_id"])
        task_id = str(result["task_id"])
        agent_id = str(result["agent"]["agent_id"])
        with self._transaction() as con:
            agent_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent_row is None:
                raise TaskNotFoundError(f"agent not registered: {agent_id}")
            agent_profile = validate_agent_profile(_decode(agent_row["profile_json"]))
            for key in ("provider", "model", "model_version"):
                if result["agent"][key] != agent_profile[key]:
                    raise TaskStoreError(f"result agent identity does not match registered {key}")
            if agent_profile["cost_profile"]["currency"] != result["usage"]["currency"]:
                raise TaskStoreError("result currency does not match the registered agent pricing")
            result["usage"]["direct_cost"] = self._generation_cost(
                agent_profile["cost_profile"], result["usage"]
            )
            result["usage"]["pricing_source"] = agent_profile["cost_profile"]["pricing_source"]
            encoded = _json(result)
            existing = con.execute(
                "SELECT result_json, task_id FROM results WHERE result_id=?", (result_id,)
            ).fetchone()
            if existing:
                if existing["result_json"] != encoded or existing["task_id"] != task_id:
                    raise TaskStoreError("result_id already exists with different content")
                return self._run_status_in_transaction(con, str(result["run_id"]))
            row = self._owned_lease(con, task_id, agent_id, lease_token)
            task = _decode(row["task_json"])
            result_domain = result["output"].get("domain")
            if result_domain is not None and result_domain != task["domain"]:
                raise TaskStoreError(
                    f"result domain {result_domain!r} does not match task domain {task['domain']!r}"
                )
            if task["domain"] == "ziwei_saju" and result_domain != "ziwei_saju":
                raise TaskStoreError(
                    "ziwei_saju tasks require result.output.domain='ziwei_saju'"
                )
            if task["task_type"] == "verification":
                raise TaskStoreError("verification tasks must use submit_review, not submit_result")
            result_domain = result["output"].get("domain")
            if result_domain is not None and result_domain != task["domain"]:
                raise TaskStoreError(
                    f"result domain {result_domain!r} does not match task domain {task['domain']!r}"
                )
            if task["domain"] == "ziwei_saju" and result_domain != "ziwei_saju":
                raise TaskStoreError(
                    "ziwei_saju tasks require result.output.domain='ziwei_saju'"
                )
            if result["run_id"] != row["run_id"] or int(result["attempt"]) != int(row["attempt"]):
                raise TaskStoreError("result run_id or attempt does not match the active task lease")
            run_row = con.execute(
                "SELECT run_json FROM runs WHERE run_id=?", (row["run_id"],)
            ).fetchone()
            if run_row is None:
                raise TaskNotFoundError(f"run not found: {row['run_id']}")
            run = _decode(run_row["run_json"])
            if result["usage"]["currency"] != run["cost_policy"]["currency"]:
                raise TaskStoreError("result currency does not match the run cost policy")
            if agent_profile["cost_profile"]["currency"] != run["cost_policy"]["currency"]:
                raise TaskStoreError("registered agent pricing currency does not match the run")
            try:
                con.execute(
                    """
                    INSERT INTO results(result_id, task_id, attempt, agent_id, result_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (result_id, task_id, result["attempt"], agent_id, encoded, _utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                raise TaskStoreError("a result already exists for this task attempt") from exc
            new_status = "submitted"
            if result["status"] == "failed":
                new_status = "queued" if int(row["attempt"]) < int(row["max_attempts"]) else "failed"
                task["last_failed_result_id"] = result_id
                task.pop("estimated_cost_reserved", None)
                if new_status == "queued":
                    failed_agents = set(task["input"].get("failed_agent_ids", []))
                    failed_agents.add(agent_id)
                    task["input"]["failed_agent_ids"] = sorted(failed_agents)
                task.pop("result_id", None)
            else:
                material_claims = [
                    claim for claim in result["claims"]
                    if claim["material"] and claim["claim_type"] in {"factual", "inference"}
                ]
                run_policy = run["execution_policy"]
                requires_review = (
                    bool(material_claims)
                    or task["input"].get("requires_code_review") is True
                    or run_policy["strategy"] == "single_with_review"
                )
                if requires_review and run_policy["strategy"] not in {
                    "single_with_review", "read_only_exploration", "parallel_independent"
                }:
                    raise TaskStoreError(
                        "this result requires independent review; choose a strategy that supports it"
                    )
                task["result_id"] = result_id
                if requires_review:
                    remaining_reserve = max(
                        0.0,
                        float(task.get("estimated_cost_reserved", 0.0))
                        - float(result["usage"]["direct_cost"]),
                    )
                    verification_id = self._create_verification_task(
                        con,
                        run_id=row["run_id"],
                        producer_task=task,
                        result=result,
                        reserved_cost=remaining_reserve,
                    )
                    task["verification_task_id"] = verification_id
                    task.pop("estimated_cost_reserved", None)
                    new_status = "submitted"
                else:
                    task.pop("estimated_cost_reserved", None)
                    new_status = "accepted"
            self._set_task(con, row, task, new_status)
            self._event(
                con,
                run_id=row["run_id"],
                task_id=task_id,
                agent_id=agent_id,
                event_type="result_submitted" if result["status"] == "submitted" else "attempt_failed",
                payload={
                    "result_id": result_id,
                    "attempt": result["attempt"],
                    "direct_cost": result["usage"]["direct_cost"],
                    "new_task_status": new_status,
                },
            )
            self._refresh_run_status(con, row["run_id"])
            return self._run_status_in_transaction(con, row["run_id"])

    def fail_task(
        self,
        task_id: str,
        agent_id: str,
        lease_token: str,
        reason: str,
        *,
        retryable: bool = True,
    ) -> dict[str, Any]:
        reason = _required_string(reason, "reason")
        if not isinstance(retryable, bool):
            raise ValueError("retryable must be a boolean")
        with self._transaction() as con:
            row = self._owned_lease(con, task_id, agent_id, lease_token)
            task = _decode(row["task_json"])
            new_status = (
                "queued"
                if retryable and int(row["attempt"]) < int(row["max_attempts"])
                else "failed"
            )
            task["last_failure"] = reason
            if new_status == "queued":
                failed_agents = set(task["input"].get("failed_agent_ids", []))
                failed_agents.add(agent_id)
                task["input"]["failed_agent_ids"] = sorted(failed_agents)
            # fail_task has no usage payload. Preserve the current attempt's
            # estimate separately; a subsequent claim writes a fresh estimate.
            unreported_reserve = float(task.pop("estimated_cost_reserved", 0.0))
            if unreported_reserve > 0:
                task["unreported_cost_reserved"] = (
                    float(task.get("unreported_cost_reserved", 0.0))
                    + unreported_reserve
                )
            self._set_task(con, row, task, new_status)
            if new_status == "failed" and task.get("task_type") == "verification":
                self._mark_verification_parent_needs_review(con, task, reason)
            self._event(
                con,
                run_id=row["run_id"],
                task_id=task_id,
                agent_id=agent_id,
                event_type="task_failed",
                payload={
                    "attempt": int(row["attempt"]),
                    "retryable": retryable,
                    "reason": reason,
                    "new_status": new_status,
                },
            )
            self._refresh_run_status(con, row["run_id"])
            return self._run_status_in_transaction(con, row["run_id"])

    def get_verification_payload(
        self,
        task_id: str,
        agent_id: str,
        lease_token: str,
    ) -> dict[str, Any]:
        """Return the immutable result only to the agent holding its verifier lease."""
        with self._transaction() as con:
            row = self._owned_lease(con, task_id, agent_id, lease_token)
            task = _decode(row["task_json"])
            if task["task_type"] != "verification" or task["role"] != "verifier":
                raise TaskLeaseError("task is not a verification task")
            result_id = _required_string(task["input"].get("result_id"), "verification.input.result_id")
            result_row = con.execute(
                "SELECT result_json FROM results WHERE result_id=?", (result_id,)
            ).fetchone()
            if result_row is None:
                raise TaskNotFoundError(f"result not found: {result_id}")
            result = _decode(result_row["result_json"])
            if result["task_id"] != task.get("parent_task_id"):
                raise TaskStoreError("verification task is bound to a different source task")
            return {
                "verification_task": {
                    "task_id": task_id,
                    "run_id": row["run_id"],
                    "attempt": int(row["attempt"]),
                    "role": task["role"],
                    "domain": task["domain"],
                    "acceptance_criteria": task["acceptance_criteria"],
                },
                "result": result,
            }

    def submit_review(
        self,
        value: Mapping[str, Any],
        lease_token: str,
    ) -> dict[str, Any]:
        """Accept reviews only from an agent holding the bound verification-task lease."""
        review_id = str(_required_string(value.get("review_id"), "review.review_id"))
        result_id = str(_required_string(value.get("result_id"), "review.result_id"))
        review_task_id = str(_required_string(value.get("review_task_id"), "review.review_task_id"))
        reviewer_id = str(_required_string(value.get("reviewer", {}).get("agent_id"), "review.reviewer.agent_id"))

        with self._transaction() as con:
            result_row = con.execute(
                "SELECT task_id, agent_id, result_json FROM results WHERE result_id=?",
                (result_id,),
            ).fetchone()
            if result_row is None:
                raise TaskNotFoundError(f"result not found: {result_id}")
            result = _decode(result_row["result_json"])
            review = validate_review_envelope(value, result)

            reviewer_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (reviewer_id,)
            ).fetchone()
            if reviewer_row is None:
                raise TaskNotFoundError(f"reviewer agent not registered: {reviewer_id}")
            verifier = validate_agent_profile(_decode(reviewer_row["profile_json"]))
            for key in ("provider", "model", "model_version"):
                if review["reviewer"][key] != verifier[key]:
                    raise TaskStoreError(f"reviewer identity does not match registered {key}")
            if review["usage"]["currency"] != verifier["cost_profile"]["currency"]:
                raise TaskStoreError("review currency does not match registered verifier pricing")
            review["usage"]["direct_cost"] = self._generation_cost(
                verifier["cost_profile"], review["usage"]
            )
            review["usage"]["pricing_source"] = verifier["cost_profile"]["pricing_source"]
            encoded_review = _json(review)

            prior_review = con.execute(
                "SELECT review_json, result_id FROM reviews WHERE review_id=?", (review_id,)
            ).fetchone()
            if prior_review:
                if prior_review["review_json"] != encoded_review or prior_review["result_id"] != result_id:
                    raise TaskStoreError("review_id already exists with different content")
                source_task = con.execute(
                    "SELECT run_id FROM tasks WHERE task_id=?", (result_row["task_id"],)
                ).fetchone()
                if source_task is None:
                    raise TaskNotFoundError(f"task not found: {result_row['task_id']}")
                return self._run_status_in_transaction(con, source_task["run_id"])

            review_task_row = self._owned_lease(
                con, review_task_id, reviewer_id, lease_token
            )
            review_task = _decode(review_task_row["task_json"])
            if (
                review_task["task_type"] != "verification"
                or review_task["role"] != "verifier"
                or review_task["input"].get("result_id") != result_id
                or review_task.get("parent_task_id") != result["task_id"]
            ):
                raise TaskLeaseError("lease is not for the verification task bound to this result")
            if review_task_row["run_id"] != result["run_id"]:
                raise TaskLeaseError("verification task belongs to a different run")
            if reviewer_id in set(review_task["input"].get("excluded_agent_ids", [])):
                raise TaskLeaseError("this agent has already reviewed the result")

            task_row = con.execute(
                "SELECT * FROM tasks WHERE task_id=?", (result_row["task_id"],)
            ).fetchone()
            if task_row is None:
                raise TaskNotFoundError(f"task not found: {result_row['task_id']}")
            if task_row["status"] not in {"submitted", "needs_review"}:
                raise TaskStoreError(f"source task cannot be reviewed in state {task_row['status']}")
            run_row = con.execute(
                "SELECT run_json FROM runs WHERE run_id=?", (task_row["run_id"],)
            ).fetchone()
            if run_row is None:
                raise TaskNotFoundError(f"run not found: {task_row['run_id']}")
            run = _decode(run_row["run_json"])

            producer_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (result_row["agent_id"],)
            ).fetchone()
            if producer_row is None:
                raise TaskNotFoundError(f"producer agent not registered: {result_row['agent_id']}")
            producer = validate_agent_profile(_decode(producer_row["profile_json"]))
            source_task = _decode(task_row["task_json"])
            quality_ok = result_meets_quality_gate(
                result,
                review,
                producer,
                verifier,
                task_role=source_task["role"],
                domain=source_task["domain"],
                accuracy_target=run["quality_policy"]["accuracy_target"],
                hallucination_max=run["quality_policy"]["hallucination_max"],
            )

            con.execute(
                """
                INSERT INTO reviews(review_id, result_id, reviewer_agent_id, review_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_id, result_id, reviewer_id, encoded_review, _utc_now()),
            )
            self._event(
                con,
                run_id=task_row["run_id"],
                task_id=task_row["task_id"],
                agent_id=reviewer_id,
                event_type="review_submitted",
                payload={
                    "review_id": review_id,
                    "result_id": result_id,
                    "verification_task_id": review_task_id,
                    "review_status": review["status"],
                    "quality_gate_passed": quality_ok,
                    "review_cost": review["usage"]["direct_cost"],
                },
            )

            if quality_ok:
                review_task["review_id"] = review_id
                review_task.pop("estimated_cost_reserved", None)
                self._set_task(con, review_task_row, review_task, "accepted")
                source_task["review_id"] = review_id
                source_task.pop("estimated_cost_reserved", None)
                self._set_task(con, task_row, source_task, "accepted")
            else:
                excluded = set(review_task["input"].get("excluded_agent_ids", []))
                excluded.add(reviewer_id)
                review_task["input"]["excluded_agent_ids"] = sorted(excluded)
                review_task["last_review_id"] = review_id
                verdicts = {item["verdict"] for item in review["claims"]}
                explicit_rejection = review["status"] == "rejected" or "contradicted" in verdicts
                attempts_left = int(review_task_row["attempt"]) < int(review_task_row["max_attempts"])
                available_verifiers: list[dict[str, Any]] = []
                if attempts_left and not explicit_rejection:
                    fresh_after = datetime.fromtimestamp(
                        time.time() - AGENT_HEARTBEAT_TTL_SECONDS, timezone.utc
                    ).isoformat()
                    candidate_rows = con.execute(
                        "SELECT agent_id, profile_json FROM agents "
                        "WHERE status='active' AND updated_at >= ?",
                        (fresh_after,),
                    ).fetchall()
                    task_scopes = set(review_task["data_scopes"])
                    for candidate_row in candidate_rows:
                        candidate = validate_agent_profile(_decode(candidate_row["profile_json"]))
                        if candidate["agent_id"] in excluded:
                            continue
                        if not set(review_task["required_capabilities"]).issubset(set(candidate["capabilities"])):
                            continue
                        candidate_scopes = set(candidate["allowed_data_scopes"])
                        if "*" not in candidate_scopes and not task_scopes.issubset(candidate_scopes):
                            continue
                        leased = con.execute(
                            "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                            (candidate["agent_id"],),
                        ).fetchone()[0]
                        if leased < candidate["max_concurrency"]:
                            available_verifiers.append(candidate)
                ranked_verifiers = rank_qualified_agents(
                    available_verifiers,
                    role=review_task["role"],
                    domain=review_task["domain"],
                    currency=run["cost_policy"]["currency"],
                    estimated_input_tokens=review_task["input"].get("estimated_input_tokens", 0),
                    estimated_output_tokens=review_task["input"].get("estimated_output_tokens", 0),
                    estimated_cached_input_tokens=review_task["input"].get("estimated_cached_input_tokens", 0),
                    accuracy_target=run["quality_policy"]["accuracy_target"],
                    hallucination_max=run["quality_policy"]["hallucination_max"],
                )
                if explicit_rejection:
                    self._set_task(con, review_task_row, review_task, "accepted")
                    source_task["review_id"] = review_id
                    self._set_task(con, task_row, source_task, "rejected")
                elif attempts_left and ranked_verifiers:
                    # This review's actual cost is already recorded. The next
                    # verifier claim will calculate a fresh attempt reservation.
                    review_task.pop("estimated_cost_reserved", None)
                    self._set_task(con, review_task_row, review_task, "queued")
                    source_task["review_id"] = review_id
                    self._set_task(con, task_row, source_task, "needs_review")
                else:
                    self._set_task(con, review_task_row, review_task, "accepted")
                    source_task["review_id"] = review_id
                    self._set_task(con, task_row, source_task, "needs_review")

            self._refresh_run_status(con, task_row["run_id"])
            return self._run_status_in_transaction(con, task_row["run_id"])

    def _run_status_in_transaction(self, con: sqlite3.Connection, run_id: str) -> dict[str, Any]:
        run_row = con.execute(
            "SELECT run_json FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run_row is None:
            raise TaskNotFoundError(f"run not found: {run_id}")
        run = _decode(run_row["run_json"])
        tasks = [
            {
                "task_id": row["task_id"],
                "task_type": _decode(row["task_json"])["task_type"],
                "verification_task_id": _decode(row["task_json"]).get("verification_task_id"),
                "status": row["status"],
                "attempt": int(row["attempt"]),
                "max_attempts": int(row["max_attempts"]),
                "lease_owner": row["lease_owner"],
                "lease_expires_at": row["lease_expires_at"],
            }
            for row in con.execute(
                """
                SELECT task_id, task_json, status, attempt, max_attempts, lease_owner, lease_expires_at
                FROM tasks WHERE run_id=? ORDER BY created_at, task_id
                """,
                (run_id,),
            )
        ]
        actual_cost = self._get_actual_cost(con, run_id)
        reserved_cost = self._get_reserved_cost(con, run_id)
        return {
            "run": run,
            "tasks": tasks,
            "total_direct_cost": actual_cost,
            "reserved_cost": reserved_cost,
            "budget_remaining": max(
                0.0,
                float(run["cost_policy"]["max_total"]) - actual_cost - reserved_cost,
            ),
            "currency": run["cost_policy"]["currency"],
        }

    def get_run_status(self, run_id: str) -> dict[str, Any]:
        with self._transaction() as con:
            self._reap_expired_leases(con, time.time())
            return self._run_status_in_transaction(con, run_id)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._transaction() as con:
            run_row = con.execute(
                "SELECT run_json FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run_row is None:
                raise TaskNotFoundError(f"run not found: {run_id}")
            run = _decode(run_row["run_json"])
            now = _utc_now()
            run["status"] = "cancelled"
            run["updated_at"] = now
            con.execute(
                "UPDATE runs SET status='cancelled', run_json=?, updated_at=? WHERE run_id=?",
                (_json(run), now, run_id),
            )
            rows = con.execute(
                """
                SELECT * FROM tasks WHERE run_id=?
                AND status IN ('queued', 'leased', 'submitted', 'needs_review')
                """,
                (run_id,),
            ).fetchall()
            for row in rows:
                task = _decode(row["task_json"])
                self._set_task(con, row, task, "cancelled")
            self._event(con, run_id=run_id, event_type="run_cancelled", payload={"cancelled_tasks": len(rows)})
            return self._run_status_in_transaction(con, run_id)
