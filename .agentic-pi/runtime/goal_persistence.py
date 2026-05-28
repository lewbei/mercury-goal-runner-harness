"""goal_persistence.py
-------------------
Provides persistence for attempt logging, dead-end detection, retry-prompt generation
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

# Optional file-locking support - if unavailable we fall back to naive writes.
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

@dataclass
class GoalState:
    """Tracks high-level execution state for a goal."""
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
    """Base class for all persistence-related errors."""
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
                # If locking fails we still return the file - the caller will see
                # the exception and can decide to retry.
                f.close()
                raise AttemptLogError(f"Failed to acquire lock on {path}: {exc}")
        return f

    # ---------------------------------------------------------------------
    # Public API - attempt log
    # ---------------------------------------------------------------------
    # ---------------------------------------------------------------------
    # Public API - retry prompt
    # ---------------------------------------------------------------------
    # ---------------------------------------------------------------------
    # Public API - goal state
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
            # Atomic replace - works on Windows and POSIX.
            os.replace(tmp_path, self.goal_state_path)
        except Exception as exc:  # pragma: no cover
            raise GoalStateError(f"Failed to save goal state: {exc}")

    # ---------------------------------------------------------------------
    # Convenience wrappers used by the orchestrator
    # ---------------------------------------------------------------------
