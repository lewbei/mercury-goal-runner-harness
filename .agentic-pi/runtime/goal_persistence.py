"""goal_persistence.py
-------------------
Provides persistence for attempt logging, dead‑end detection, retry‑prompt generation
and overall goal state tracking.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

# Optional file‑locking support – if unavailable we fall back to naïve writes.
try:
    import portalocker  # type: ignore
    _HAS_LOCK = True
except Exception:  # pragma: no cover
    _HAS_LOCK = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Attempt:
    """A single attempt record stored in ``attempt_log.jsonl``."""
    approach: str
    failure_reason: str
    what_was_tried: str
    timestamp: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Attempt":
        return Attempt(
            approach=data.get("approach", ""),
            failure_reason=data.get("failure_reason", ""),
            what_was_tried=data.get("what_was_tried", ""),
            timestamp=data.get("timestamp", ""),
        )

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False) + "\n"


@dataclass
class GoalState:
    """Tracks high‑level execution state for a goal."""
    phase: str = "initial"
    attempts_count: int = 0
    approaches_tried: List[str] = None
    stuck_subgoals: List[str] = None
    remaining_subgoals: List[str] = None

    def __post_init__(self) -> None:
        if self.approaches_tried is None:
            self.approaches_tried = []
        if self.stuck_subgoals is None:
            self.stuck_subgoals = []
        if self.remaining_subgoals is None:
            self.remaining_subgoals = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "attempts_count": self.attempts_count,
            "approaches_tried": self.approaches_tried,
            "stuck_subgoals": self.stuck_subgoals,
            "remaining_subgoals": self.remaining_subgoals,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "GoalState":
        return GoalState(
            phase=data.get("phase", "initial"),
            attempts_count=data.get("attempts_count", 0),
            approaches_tried=data.get("approaches_tried", []),
            stuck_subgoals=data.get("stuck_subgoals", []),
            remaining_subgoals=data.get("remaining_subgoals", []),
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PersistenceError(RuntimeError):
    """Base class for all persistence‑related errors."""
    pass

class AttemptLogError(PersistenceError):
    """Raised when reading or writing the attempt log fails."""
    pass

class GoalStateError(PersistenceError):
    """Raised when loading or saving the goal state fails."""
    pass


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class GoalPersistence:
    """Encapsulates all persistence operations for a goal execution.

    All file paths are resolved relative to ``base_dir``. By default the class
    operates in the current working directory, which makes it easy to use from
    the orchestrator or from unit tests.
    """

    def __init__(self, base_dir: Path | str = Path.cwd()) -> None:
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.attempt_log_path = self.base_dir / "attempt_log.jsonl"
        self.goal_state_path = self.base_dir / "goal_state.json"
        self._ensure_files_exist()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _ensure_files_exist(self) -> None:
        """Create empty log and state files if they are missing.

        The state file is initialised with the default ``GoalState``.
        """
        if not self.attempt_log_path.exists():
            self.attempt_log_path.touch()
        if not self.goal_state_path.exists():
            self.save_state(GoalState())

    def _locked_open(self, path: Path, mode: str):
        """Open a file with an exclusive lock if ``portalocker`` is available.

        The returned file object must be used as a context manager.
        """
        f = open(path, mode, encoding="utf-8")
        if _HAS_LOCK:
            try:
                portalocker.lock(f, portalocker.LOCK_EX)
            except Exception as exc:  # pragma: no cover
                # If locking fails we still return the file – the caller will see
                # the exception and can decide to retry.
                f.close()
                raise AttemptLogError(f"Failed to acquire lock on {path}: {exc}")
        return f

    # ---------------------------------------------------------------------
    # Public API – attempt log
    # ---------------------------------------------------------------------
    def log_attempt(
        self,
        approach: str,
        failure_reason: str,
        what_was_tried: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Append a new attempt record to ``attempt_log.jsonl``.

        Parameters
        ----------
        approach:
            Identifier of the approach that was tried (e.g. a prompt name).
        failure_reason:
            Human‑readable reason why the attempt failed.
        what_was_tried:
            A short description of the concrete action taken.
        timestamp:
            Optional ``datetime``; if omitted the current UTC time is used.
        """
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        attempt = Attempt(
            approach=approach,
            failure_reason=failure_reason,
            what_was_tried=what_was_tried,
            timestamp=ts,
        )
        try:
            with self._locked_open(self.attempt_log_path, "a") as f:
                f.write(attempt.to_json_line())
        except Exception as exc:  # pragma: no cover
            raise AttemptLogError(f"Failed to write attempt log: {exc}")

    def load_attempts(self) -> List[Attempt]:
        """Read all attempt records from ``attempt_log.jsonl``.

        Malformed lines are skipped with a warning written to ``stderr``.
        """
        attempts: List[Attempt] = []
        try:
            with open(self.attempt_log_path, "r", encoding="utf-8") as f:
                for line_number, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        attempts.append(Attempt.from_dict(data))
                    except json.JSONDecodeError as exc:
                        print(
                            f"[AttemptLog] Skipping malformed line {line_number}: {exc}",
                            file=sys.stderr,
                        )
        except Exception as exc:  # pragma: no cover
            raise AttemptLogError(f"Failed to read attempt log: {exc}")
        return attempts

    # ---------------------------------------------------------------------
    # Public API – retry prompt
    # ---------------------------------------------------------------------
    def build_retry_prompt(self, subgoal_id: str) -> str:
        """Construct a retry prompt that lists *all* failed approaches for ``subgoal_id``.

        The prompt ends with an explicit instruction **"do NOT try these again"**.
        The function assumes that the ``approach`` field is prefixed with the sub‑goal
        identifier in the form ``"subgoal:{subgoal_id}:{approach_name}"``.
        """
        attempts = self.load_attempts()
        # Filter attempts that belong to the sub‑goal.
        relevant = [
            a
            for a in attempts
            if a.approach.startswith(f"subgoal:{subgoal_id}:")
        ]
        if not relevant:
            return f"Retry for sub‑goal {subgoal_id}: No previous failures recorded."
        lines = [
            f"- Approach: {a.approach.split(':')[-1]}\n  Reason: {a.failure_reason}\n  Details: {a.what_was_tried}"
            for a in relevant
        ]
        prompt = (
            f"You have previously attempted the sub‑goal '{subgoal_id}' and failed.\n"
            "The failed attempts are listed below:\n\n"
            + "\n".join(lines)
            + "\n\nPlease propose a new approach, **do NOT try these again**."
        )
        return prompt

    # ---------------------------------------------------------------------
    # Public API – dead‑end detection
    # ---------------------------------------------------------------------
    def detect_dead_end(self, subgoal_id: str, threshold: int = 3) -> bool:
        """Return ``True`` if the same ``failure_reason`` has occurred ``threshold`` times for ``subgoal_id``.

        The function updates the goal state by marking the sub‑goal as stuck when the
        condition is met.
        """
        attempts = self.load_attempts()
        # Gather failure reasons for the sub‑goal.
        reasons: Dict[str, int] = {}
        for a in attempts:
            if a.approach.startswith(f"subgoal:{subgoal_id}:"):
                reasons[a.failure_reason] = reasons.get(a.failure_reason, 0) + 1
        for reason, count in reasons.items():
            if count >= threshold:
                # Mark sub‑goal as stuck.
                self.mark_subgoal_stuck(subgoal_id)
                return True
        return False

    # ---------------------------------------------------------------------
    # Public API – goal state
    # ---------------------------------------------------------------------
    def load_state(self) -> GoalState:
        """Load ``goal_state.json`` and return a ``GoalState`` instance.

        If the file is missing or corrupted, a fresh ``GoalState`` is returned and
        the error is logged to ``stderr``.
        """
        try:
            with open(self.goal_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return GoalState.from_dict(data)
        except Exception as exc:  # pragma: no cover
            print(
                f"[GoalState] Failed to load state (will reset): {exc}",
                file=sys.stderr,
            )
            return GoalState()

    def save_state(self, state: GoalState) -> None:
        """Atomically write ``state`` to ``goal_state.json``.

        The file is first written to a temporary ``*.tmp`` file and then renamed.
        """
        tmp_path = self.goal_state_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            # Atomic replace – works on Windows and POSIX.
            os.replace(tmp_path, self.goal_state_path)
        except Exception as exc:  # pragma: no cover
            raise GoalStateError(f"Failed to save goal state: {exc}")

    def mark_subgoal_stuck(self, subgoal_id: str) -> None:
        """Add ``subgoal_id`` to the ``stuck_subgoals`` list in the state file.
        """
        state = self.load_state()
        if subgoal_id not in state.stuck_subgoals:
            state.stuck_subgoals.append(subgoal_id)
            self.save_state(state)

    def update_phase(self, new_phase: str) -> None:
        """Set the current execution phase and persist the change."""
        state = self.load_state()
        state.phase = new_phase
        self.save_state(state)

    def add_approach(self, approach: str) -> None:
        """Record a new approach in the state (used for quick lookup)."""
        state = self.load_state()
        if approach not in state.approaches_tried:
            state.approaches_tried.append(approach)
            state.attempts_count += 1
            self.save_state(state)

    # ---------------------------------------------------------------------
    # Convenience wrappers used by the orchestrator
    # ---------------------------------------------------------------------
    def record_failure(
        self,
        subgoal_id: str,
        approach_name: str,
        failure_reason: str,
        what_was_tried: str,
    ) -> None:
        """High‑level helper that logs a failure and updates the state.

        ``approach_name`` is automatically prefixed with the sub‑goal identifier.
        """
        full_approach = f"subgoal:{subgoal_id}:{approach_name}"
        self.log_attempt(full_approach, failure_reason, what_was_tried)
        self.add_approach(full_approach)

    def maybe_mark_stuck(self, subgoal_id: str, threshold: int = 3) -> bool:
        """Convenient wrapper that checks for dead‑end and returns ``True`` if stuck."""
        return self.detect_dead_end(subgoal_id, threshold)
