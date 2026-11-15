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

    @staticmethod
    def _validate_label(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")

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
        if plan_id in self._used_plans:
            self._terminal_reason = "duplicate_redesign"
            return False

        self._used_plans.add(plan_id)
        self.redesigns += 1
        self.strategy = strategy.strip()
        self.hypothesis = hypothesis.strip()
        self._actions.clear()
        self._errors.clear()
        self._last_progress = None
        self._no_progress_steps = 0
        self._trip_reasons = ()
        return True

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
        }
