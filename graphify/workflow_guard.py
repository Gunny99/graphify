"""Bounded repeated-action and no-progress protection for workflow runs.

This module is deliberately pure: the controller owns persistence, scheduling,
checkpointing and cancellation. The guard only decides whether work may
continue, must be redesigned, or must stop.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
from typing import Any


_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(r"\b0x[0-9a-f]{6,}\b", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class GuardDecision:
    """A serializable decision returned after each observed workflow step."""

    status: str
    reasons: tuple[str, ...]
    action_repeats: int
    error_repeats: int
    no_progress_steps: int
    redesigns: int

    @property
    def should_stop(self) -> bool:
        return self.status == "stop"

    @property
    def needs_redesign(self) -> bool:
        return self.status == "redesign"


def _normalize(value: Any) -> str:
    text = str(value).strip().casefold()
    text = _UUID_RE.sub("<uuid>", text)
    text = _ADDRESS_RE.sub("<address>", text)
    return _SPACE_RE.sub(" ", text)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_normalize(value).encode("utf-8")).hexdigest()


class WorkflowLoopGuard:
    """Detect repeated actions/errors and no-progress loops with bounded redesign.

    The default threshold is three observations. A redesign must introduce a
    previously unseen strategy+hypothesis pair; renaming an identical retry
    does not reset the guard. The controller should persist each decision as a
    run event and checkpoint before acting on it.
    """

    def __init__(
        self,
        *,
        strategy: str,
        hypothesis: str,
        repeated_action_limit: int = 3,
        repeated_error_limit: int = 3,
        no_progress_limit: int = 3,
        max_redesigns: int = 2,
    ) -> None:
        self._validate_label(strategy, "strategy")
        self._validate_label(hypothesis, "hypothesis")
        for name, value in (
            ("repeated_action_limit", repeated_action_limit),
            ("repeated_error_limit", repeated_error_limit),
            ("no_progress_limit", no_progress_limit),
            ("max_redesigns", max_redesigns),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1")

        self.repeated_action_limit = repeated_action_limit
        self.repeated_error_limit = repeated_error_limit
        self.no_progress_limit = no_progress_limit
        self.max_redesigns = max_redesigns
        self.redesigns = 0
        self.strategy = strategy.strip()
        self.hypothesis = hypothesis.strip()
        self._used_plans = {self._plan_fingerprint(self.strategy, self.hypothesis)}
        self._actions: Counter[str] = Counter()
        self._errors: Counter[str] = Counter()
        self._last_progress: str | None = None
        self._no_progress_steps = 0
        self._trip_reasons: tuple[str, ...] = ()
        self._terminal_reason: str | None = None
        self._last_redesign_rationale: str | None = None

    @staticmethod
    def _validate_label(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        if len(value) > 512 or chr(10) in value or chr(13) in value:
            raise ValueError(f"{name} must be a single line of at most 512 characters")

    @staticmethod
    def _plan_fingerprint(strategy: str, hypothesis: str) -> str:
        return _fingerprint(f"{_normalize(strategy)}\n{_normalize(hypothesis)}")

    def _decision(self, status: str, reasons: tuple[str, ...]) -> GuardDecision:
        return GuardDecision(
            status=status,
            reasons=reasons,
            action_repeats=max(self._actions.values(), default=0),
            error_repeats=max(self._errors.values(), default=0),
            no_progress_steps=self._no_progress_steps,
            redesigns=self.redesigns,
        )

    def observe(
        self,
        action: str,
        *,
        error: BaseException | str | None = None,
        progress_token: str | None = None,
    ) -> GuardDecision:
        """Observe one action. A changed progress token resets the loop window."""
        self._validate_label(action, "action")
        if self._terminal_reason:
            return self._decision("stop", (self._terminal_reason,))
        if self._trip_reasons:
            return self._decision("redesign", self._trip_reasons)

        if progress_token is not None:
            if not isinstance(progress_token, str) or len(progress_token) > 256:
                raise ValueError("progress_token must be a string of at most 256 characters")
            token = _fingerprint(progress_token)
            if self._last_progress is None:
                self._last_progress = token
            elif token != self._last_progress:
                self._last_progress = token
                self._actions.clear()
                self._errors.clear()
                self._no_progress_steps = 0
            else:
                self._no_progress_steps += 1

        action_key = _fingerprint(action)
        self._actions[action_key] += 1
        current_error_repeats = 0
        if error is not None:
            error_type = type(error).__name__ if isinstance(error, BaseException) else "Error"
            error_text = str(error) if isinstance(error, BaseException) else error
            error_key = _fingerprint(f"{error_type}: {_normalize(error_text)}")
            self._errors[error_key] += 1
            current_error_repeats = self._errors[error_key]

        reasons = []
        if self._actions[action_key] >= self.repeated_action_limit:
            reasons.append("repeated_action")
        if current_error_repeats >= self.repeated_error_limit:
            reasons.append("repeated_error")
        if self._no_progress_steps >= self.no_progress_limit:
            reasons.append("no_progress")

        if reasons:
            self._trip_reasons = tuple(reasons)
            status = "redesign" if self.redesigns < self.max_redesigns else "stop"
            if status == "stop":
                self._terminal_reason = "redesign_budget_exhausted"
                return self._decision("stop", (*self._trip_reasons, self._terminal_reason))
            return self._decision("redesign", self._trip_reasons)

        return self._decision("continue", ())

    def propose_redesign(
        self,
        *,
        strategy: str,
        hypothesis: str,
        rationale: str,
    ) -> bool:
        """Accept only a genuinely new plan after a loop trip.

        Returns False when no redesign is due, the plan was already attempted,
        or the bounded redesign budget is exhausted. A False result means the
        controller must stop or escalate; it must not resume the old plan.
        """
        self._validate_label(strategy, "strategy")
        self._validate_label(hypothesis, "hypothesis")
        self._validate_label(rationale, "rationale")
        if not self._trip_reasons or self._terminal_reason:
            return False
        if self.redesigns >= self.max_redesigns:
            self._terminal_reason = "redesign_budget_exhausted"
            return False

        plan_id = self._plan_fingerprint(strategy, hypothesis)
        if (
            plan_id in self._used_plans
            or _normalize(strategy) == _normalize(self.strategy)
            or _normalize(hypothesis) == _normalize(self.hypothesis)
        ):
            self._terminal_reason = "duplicate_redesign"
            return False

        self._used_plans.add(plan_id)
        self.redesigns += 1
        self.strategy = strategy.strip()
        self.hypothesis = hypothesis.strip()
        self._last_redesign_rationale = rationale.strip()
        self._actions.clear()
        self._errors.clear()
        self._last_progress = None
        self._no_progress_steps = 0
        self._trip_reasons = ()
        return True

    def to_state(self) -> dict[str, Any]:
        """Serialize counters and fingerprints for durable event-ledger recovery."""
        return {
            "schema_version": 1,
            "strategy": self.strategy,
            "hypothesis": self.hypothesis,
            "repeated_action_limit": self.repeated_action_limit,
            "repeated_error_limit": self.repeated_error_limit,
            "no_progress_limit": self.no_progress_limit,
            "max_redesigns": self.max_redesigns,
            "redesigns": self.redesigns,
            "used_plans": sorted(self._used_plans),
            "actions": dict(self._actions),
            "errors": dict(self._errors),
            "last_progress": self._last_progress,
            "no_progress_steps": self._no_progress_steps,
            "trip_reasons": list(self._trip_reasons),
            "terminal_reason": self._terminal_reason,
            "last_redesign_rationale": self._last_redesign_rationale,
        }

    @classmethod
    def from_state(cls, value: Any) -> "WorkflowLoopGuard":
        """Restore a previously serialized guard state with strict bounds."""
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("unsupported workflow guard state")
        guard = cls(
            strategy=value.get("strategy"),
            hypothesis=value.get("hypothesis"),
            repeated_action_limit=value.get("repeated_action_limit", 3),
            repeated_error_limit=value.get("repeated_error_limit", 3),
            no_progress_limit=value.get("no_progress_limit", 3),
            max_redesigns=value.get("max_redesigns", 2),
        )
        redesigns = value.get("redesigns", 0)
        no_progress = value.get("no_progress_steps", 0)
        if (
            not isinstance(redesigns, int) or isinstance(redesigns, bool)
            or not 0 <= redesigns <= guard.max_redesigns
            or not isinstance(no_progress, int) or isinstance(no_progress, bool)
            or no_progress < 0
        ):
            raise ValueError("invalid workflow guard counters")

        used_plans = value.get("used_plans")
        if not isinstance(used_plans, list) or not used_plans:
            raise ValueError("workflow guard state requires used_plans")
        if any(not isinstance(item, str) or re.fullmatch(r"[0-9a-f]{64}", item) is None for item in used_plans):
            raise ValueError("workflow guard plan fingerprints are invalid")

        def read_counter(name: str) -> Counter[str]:
            raw = value.get(name, {})
            if not isinstance(raw, dict):
                raise ValueError(f"workflow guard {name} must be an object")
            result: Counter[str] = Counter()
            for key, count in raw.items():
                if (
                    not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{64}", key) is None
                    or not isinstance(count, int) or isinstance(count, bool) or count < 1
                ):
                    raise ValueError(f"workflow guard {name} contains an invalid counter")
                result[key] = count
            return result

        last_progress = value.get("last_progress")
        if last_progress is not None and (
            not isinstance(last_progress, str)
            or re.fullmatch(r"[0-9a-f]{64}", last_progress) is None
        ):
            raise ValueError("workflow guard last_progress is invalid")
        reasons = value.get("trip_reasons", [])
        if not isinstance(reasons, list) or any(
            item not in {"repeated_action", "repeated_error", "no_progress"} for item in reasons
        ):
            raise ValueError("workflow guard trip_reasons are invalid")
        terminal = value.get("terminal_reason")
        if terminal is not None and terminal not in {"redesign_budget_exhausted", "duplicate_redesign"}:
            raise ValueError("workflow guard terminal_reason is invalid")
        rationale = value.get("last_redesign_rationale")
        if rationale is not None and (not isinstance(rationale, str) or len(rationale) > 500):
            raise ValueError("workflow guard redesign rationale is invalid")

        guard.redesigns = redesigns
        guard._used_plans = set(used_plans)
        guard._actions = read_counter("actions")
        guard._errors = read_counter("errors")
        guard._last_progress = last_progress
        guard._no_progress_steps = no_progress
        guard._trip_reasons = tuple(reasons)
        guard._terminal_reason = terminal
        guard._last_redesign_rationale = rationale
        return guard

    def snapshot(self) -> dict[str, Any]:
        """Return compact metadata suitable for a workflow event."""
        return {
            "strategy": self.strategy,
            "hypothesis": self.hypothesis,
            "redesigns": self.redesigns,
            "max_redesigns": self.max_redesigns,
            "action_repeats": max(self._actions.values(), default=0),
            "error_repeats": max(self._errors.values(), default=0),
            "no_progress_steps": self._no_progress_steps,
            "tripped_reasons": list(self._trip_reasons),
            "terminal_reason": self._terminal_reason,
            "last_redesign_rationale": self._last_redesign_rationale,
        }
