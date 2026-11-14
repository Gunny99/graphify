"""SQLite-backed durable task queue for independent Graphify agents.

The store is provider-neutral. Agents are expected to access it through the
Graphify MCP server, not by opening the database file directly.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from graphify.orchestration import (
    OrchestrationValidationError,
    estimate_end_to_end_cost,
    rank_qualified_agents,
    result_meets_quality_gate,
    validate_agent_profile,
    validate_result_envelope,
    validate_review_envelope,
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
        with self._connect() as con:
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
                    result_id TEXT NOT NULL UNIQUE REFERENCES results(result_id) ON DELETE CASCADE,
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

    def _refresh_run_status(self, con: sqlite3.Connection, run_id: str) -> str:
        row = con.execute(
            "SELECT run_json FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise TaskNotFoundError(f"run not found: {run_id}")
        run = _decode(row["run_json"])
        if run["status"] == "cancelled":
            return "cancelled"
        statuses = [
            item["status"]
            for item in con.execute("SELECT status FROM tasks WHERE run_id=?", (run_id,))
        ]
        if statuses and all(status == "accepted" for status in statuses):
            status = "accepted"
        elif any(status in {"failed", "rejected", "blocked"} for status in statuses):
            status = "failed"
        elif any(status == "needs_review" for status in statuses):
            status = "provisional"
        elif any(status == "submitted" for status in statuses):
            status = "awaiting_review"
        elif any(status == "leased" for status in statuses):
            status = "running"
        else:
            status = "queued"
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
            SELECT task_id, run_id, task_json, attempt, max_attempts
            FROM tasks
            WHERE status='leased' AND lease_expires_at <= ?
            """,
            (now_epoch,),
        ).fetchall()
        changed_runs: set[str] = set()
        for row in rows:
            task = _decode(row["task_json"])
            attempt = int(row["attempt"])
            status = "failed" if attempt >= int(row["max_attempts"]) else "queued"
            self._set_task(con, row, task, status)
            self._event(
                con,
                run_id=row["run_id"],
                task_id=row["task_id"],
                event_type="lease_expired",
                payload={"attempt": attempt, "new_status": status},
            )
            changed_runs.add(row["run_id"])
        for run_id in changed_runs:
            self._refresh_run_status(con, run_id)

    def register_agent(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Register a trusted agent profile; quality profiles must be evaluator-owned."""
        profile = validate_agent_profile(value)
        agent_id = str(profile["agent_id"])
        now = _utc_now()
        with self._transaction() as con:
            active = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                (agent_id,),
            ).fetchone()[0]
            existing = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if existing and active:
                previous = _decode(existing["profile_json"])
                identity_keys = ("provider", "model", "model_version")
                if any(previous[key] != profile[key] for key in identity_keys):
                    raise TaskStoreError("cannot change an agent model identity while it owns leased tasks")
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
            agent_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent_row is None:
                raise TaskNotFoundError(f"agent not registered: {agent_id}")
            agent = validate_agent_profile(_decode(agent_row["profile_json"]))
            if agent["status"] != "active":
                return None
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
                if _expired(task.get("deadline_at"), now_dt):
                    self._set_task(con, row, task, "failed")
                    self._event(
                        con, run_id=row["run_id"], task_id=row["task_id"],
                        event_type="deadline_expired", payload={"deadline_at": task.get("deadline_at")},
                    )
                    self._refresh_run_status(con, row["run_id"])
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

                # Re-rank currently available agents so polling order cannot make
                # a more expensive qualified model steal work from a cheaper one.
                available_agents: list[dict[str, Any]] = []
                agent_rows = con.execute(
                    "SELECT agent_id, profile_json FROM agents WHERE status='active'"
                ).fetchall()
                for other_row in agent_rows:
                    other = validate_agent_profile(_decode(other_row["profile_json"]))
                    if not set(task["required_capabilities"]).issubset(set(other["capabilities"])):
                        continue
                    leased = con.execute(
                        "SELECT COUNT(*) FROM tasks WHERE lease_owner=? AND status='leased'",
                        (other["agent_id"],),
                    ).fetchone()[0]
                    if leased < other["max_concurrency"]:
                        available_agents.append(other)
                ranked = rank_qualified_agents(
                    available_agents,
                    role=task["role"],
                    domain=task["domain"],
                    currency=run["cost_policy"]["currency"],
                    estimated_input_tokens=int(task["input"].get("estimated_input_tokens", 0)),
                    estimated_output_tokens=int(task["input"].get("estimated_output_tokens", 0)),
                    estimated_cached_input_tokens=int(task["input"].get("estimated_cached_input_tokens", 0)),
                    accuracy_target=run["quality_policy"]["accuracy_target"],
                    hallucination_max=run["quality_policy"]["hallucination_max"],
                )
                if not ranked or ranked[0]["agent_id"] != agent_id:
                    continue

                spent = self._get_actual_cost(con, row["run_id"])
                max_total = float(run["cost_policy"]["max_total"])
                expected = float(ranked[0]["estimated_total_cost"])
                if spent + expected > max_total:
                    continue
                if task.get("cost_budget"):
                    task_budget = task["cost_budget"]
                    if task_budget["currency"] != run["cost_policy"]["currency"]:
                        continue
                    if expected > float(task_budget["max_total"]):
                        continue

                next_attempt = int(row["attempt"]) + 1
                task["attempt"] = next_attempt
                task["lease_expires_at"] = expires_at
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
        supplied_hash = _token_hash(_string(lease_token, "lease_token"))
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

    def submit_result(self, value: Mapping[str, Any], lease_token: str) -> dict[str, Any]:
        """Persist a result for the currently leased attempt; retries are idempotent."""
        result = validate_result_envelope(value)
        result_id = str(result["result_id"])
        task_id = str(result["task_id"])
        agent_id = str(result["agent"]["agent_id"])
        encoded = _json(result)
        with self._transaction() as con:
            existing = con.execute(
                "SELECT result_json FROM results WHERE result_id=?", (result_id,)
            ).fetchone()
            if existing:
                if existing["result_json"] != encoded:
                    raise TaskStoreError("result_id already exists with different content")
                return self._run_status_in_transaction(con, str(result["run_id"]))
            row = self._owned_lease(con, task_id, agent_id, lease_token)
            task = _decode(row["task_json"])
            if result["run_id"] != row["run_id"] or int(result["attempt"]) != int(row["attempt"]):
                raise TaskStoreError("result run_id or attempt does not match the active task lease")
            agent_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent_row is None:
                raise TaskNotFoundError(f"agent not registered: {agent_id}")
            agent_profile = validate_agent_profile(_decode(agent_row["profile_json"]))
            for key in ("provider", "model", "model_version"):
                if result["agent"][key] != agent_profile[key]:
                    raise TaskStoreError(f"result agent identity does not match registered {key}")
            run_row = con.execute(
                "SELECT run_json FROM runs WHERE run_id=?", (row["run_id"],)
            ).fetchone()
            if run_row is None:
                raise TaskNotFoundError(f"run not found: {row['run_id']}")
            run = _decode(run_row["run_json"])
            if result["usage"]["currency"] != run["cost_policy"]["currency"]:
                raise TaskStoreError("result currency does not match the run cost policy")
            con.execute(
                """
                INSERT INTO results(result_id, task_id, attempt, agent_id, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (result_id, task_id, result["attempt"], agent_id, encoded, _utc_now()),
            )
            new_status = "submitted"
            if result["status"] == "failed":
                new_status = "queued" if int(row["attempt"]) < int(row["max_attempts"]) else "failed"
            task["result_id"] = result_id
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
        reason = _string(reason, "reason")
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
            self._set_task(con, row, task, new_status)
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

    def submit_review(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Store a verifier decision and advance the task only when both quality gates pass."""
        review_id = str(_string(value.get("review_id"), "review.review_id"))
        result_id = str(_string(value.get("result_id"), "review.result_id"))
        with self._transaction() as con:
            existing = con.execute(
                "SELECT review_json FROM reviews WHERE review_id=?", (review_id,)
            ).fetchone()
            if existing:
                if existing["review_json"] != _json(value):
                    raise TaskStoreError("review_id already exists with different content")
                existing_result = con.execute(
                    "SELECT task_id FROM results WHERE result_id=?", (result_id,)
                ).fetchone()
                if existing_result is None:
                    raise TaskNotFoundError(f"result not found: {result_id}")
                task_row = con.execute(
                    "SELECT run_id FROM tasks WHERE task_id=?", (existing_result["task_id"],)
                ).fetchone()
                return self._run_status_in_transaction(con, task_row["run_id"])

            result_row = con.execute(
                "SELECT task_id, agent_id, result_json FROM results WHERE result_id=?",
                (result_id,),
            ).fetchone()
            if result_row is None:
                raise TaskNotFoundError(f"result not found: {result_id}")
            result = _decode(result_row["result_json"])
            review = validate_review_envelope(value, result)
            task_row = con.execute(
                "SELECT * FROM tasks WHERE task_id=?", (result_row["task_id"],)
            ).fetchone()
            if task_row is None:
                raise TaskNotFoundError(f"task not found: {result_row['task_id']}")
            if task_row["status"] not in {"submitted", "needs_review"}:
                raise TaskStoreError(f"task cannot be reviewed in state {task_row['status']}")
            run_row = con.execute(
                "SELECT run_json FROM runs WHERE run_id=?", (task_row["run_id"],)
            ).fetchone()
            if run_row is None:
                raise TaskNotFoundError(f"run not found: {task_row['run_id']}")
            run = _decode(run_row["run_json"])
            if review["usage"]["currency"] != run["cost_policy"]["currency"]:
                raise TaskStoreError("review currency does not match the run cost policy")
            producer_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (result_row["agent_id"],)
            ).fetchone()
            verifier_id = review["reviewer"]["agent_id"]
            verifier_row = con.execute(
                "SELECT profile_json FROM agents WHERE agent_id=?", (verifier_id,)
            ).fetchone()
            if producer_row is None or verifier_row is None:
                raise TaskNotFoundError("producer or verifier agent is not registered")
            producer = validate_agent_profile(_decode(producer_row["profile_json"]))
            verifier = validate_agent_profile(_decode(verifier_row["profile_json"]))
            quality_ok = result_meets_quality_gate(
                result,
                review,
                producer,
                verifier,
                task_role=task_row["task_json"] and _decode(task_row["task_json"])["role"],
                domain=_decode(task_row["task_json"])["domain"],
                accuracy_target=run["quality_policy"]["accuracy_target"],
                hallucination_max=run["quality_policy"]["hallucination_max"],
            )
            new_status = "accepted" if quality_ok else (
                "rejected" if review["status"] == "rejected" else "needs_review"
            )
            con.execute(
                """
                INSERT INTO reviews(review_id, result_id, reviewer_agent_id, review_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_id, result_id, verifier_id, _json(review), _utc_now()),
            )
            task = _decode(task_row["task_json"])
            task["review_id"] = review_id
            self._set_task(con, task_row, task, new_status)
            self._event(
                con,
                run_id=task_row["run_id"],
                task_id=task_row["task_id"],
                agent_id=verifier_id,
                event_type="review_submitted",
                payload={
                    "review_id": review_id,
                    "result_id": result_id,
                    "review_status": review["status"],
                    "quality_gate_passed": quality_ok,
                    "task_status": new_status,
                    "review_cost": review["usage"]["direct_cost"],
                },
            )
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
                "status": row["status"],
                "attempt": int(row["attempt"]),
                "max_attempts": int(row["max_attempts"]),
                "lease_owner": row["lease_owner"],
                "lease_expires_at": row["lease_expires_at"],
            }
            for row in con.execute(
                """
                SELECT task_id, status, attempt, max_attempts, lease_owner, lease_expires_at
                FROM tasks WHERE run_id=? ORDER BY created_at, task_id
                """,
                (run_id,),
            )
        ]
        return {
            "run": run,
            "tasks": tasks,
            "total_direct_cost": self._get_actual_cost(con, run_id),
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
