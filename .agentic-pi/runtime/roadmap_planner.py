# .agentic-pi/runtime/roadmap_planner.py
"""Roadmap Planner

Reads a goal contract, decomposes it into ordered sub‑goals, writes a
milestone plan and a corresponding plan graph, and updates execution
state via GoalPersistence.

The implementation is deterministic and does not rely on external
LLM calls, making it reproducible and easy to test.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any

# Import the persistence helper from the same package.
from goal_persistence import GoalPersistence

# Optional validator – imported only for type checking, not used at runtime.
# from validate_milestone_plan import validate_milestone_plan

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class RoadmapPlannerError(RuntimeError):
    """Base class for all roadmap planner errors."""
    pass

class GoalContractError(RoadmapPlannerError):
    """Raised when the goal contract cannot be loaded or is malformed."""
    pass

class DecompositionError(RoadmapPlannerError):
    """Raised when sub‑goal generation fails."""
    pass

# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class SubGoal:
    """A single sub‑goal entry in the milestone plan."""
    goal_id: str
    description: str
    depends_on: List[str]
    estimated_attempts: int
    risk_level: str
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# --------------------------------------------------------------------------- #
# Core functions
# --------------------------------------------------------------------------- #

def load_goal_contract(path: Path) -> Dict[str, Any]:
    """Load the goal contract JSON.

    Parameters
    ----------
    path: Path
        Path to ``goal_contract.json``.

    Returns
    -------
    dict
        Parsed contract.

    Raises
    ------
    GoalContractError
        If the file does not exist or contains invalid JSON.
    """
    if not path.is_file():
        raise GoalContractError(f"Contract file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            contract = json.load(f)
        return contract
    except json.JSONDecodeError as exc:
        raise GoalContractError(f"Invalid JSON in contract: {exc}") from exc
    except OSError as exc:
        raise GoalContractError(f"Failed to read contract: {exc}") from exc


def decompose_goal(contract: Dict[str, Any]) -> List[SubGoal]:
    """Deterministically decompose a contract into sub‑goals.

    The heuristic creates four phases: Analyze, Design, Implement,
    Validate. Each phase depends on the previous one.

    Parameters
    ----------
    contract: dict
        The goal contract.

    Returns
    -------
    List[SubGoal]
        Ordered sub‑goals.

    Raises
    ------
    DecompositionError
        If required fields are missing or empty.
    """
    description = contract.get("description", "").strip()
    if not description:
        raise DecompositionError("Contract description is empty.")

    # Simple heuristic – split description into sentences (otherwise use whole text)
    sentences = [s.strip() for s in description.split(".") if s.strip()]
    # Ensure at least one sentence per phase; if not enough, repeat the description.
    phases = ["Analyze", "Design", "Implement", "Validate"]
    subgoals: List[SubGoal] = []

    for idx, phase in enumerate(phases):
        # Use a sentence if available, otherwise reuse the description.
        desc = sentences[idx] if idx < len(sentences) else description
        goal_id = f"sg_{idx+1:03d}"
        depends_on = [f"sg_{idx:03d}"] if idx > 0 else []
        risk = "low" if idx < 2 else ("medium" if idx == 2 else "high")
        subgoal = SubGoal(
            goal_id=goal_id,
            description=f"{phase}: {desc}",
            depends_on=depends_on,
            estimated_attempts=1,
            risk_level=risk,
        )
        subgoals.append(subgoal)

    return subgoals


def write_milestone_plan(subgoals: List[SubGoal], out_path: Path) -> None:
    """Write the milestone plan JSON atomically.

    Parameters
    ----------
    subgoals: List[SubGoal]
    out_path: Path
    """
    data = [sg.to_dict() for sg in subgoals]
    tmp_path = out_path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(out_path)
    except OSError as exc:
        raise RoadmapPlannerError(f"Failed to write milestone plan: {exc}") from exc


def write_plan_graph(subgoals: List[SubGoal], out_path: Path) -> None:
    """Write a minimal plan graph linking the milestone node to sub‑goals.

    The graph follows the platform‑required schema:
    {
        "nodes": [...],
        "edges": [...]
    }

    Parameters
    ----------
    subgoals: List[SubGoal]
    out_path: Path
    """
    nodes = [
        {"node_id": "milestone", "type": "task"},
    ]
    edges = []

    for sg in subgoals:
        artifact_id = sg.goal_id
        artifact_path = f"{artifact_id}.json"
        nodes.append(
            {
                "node_id": artifact_id,
                "type": "artifact",
                "path": artifact_path,
                "artifact_id": artifact_id,
            }
        )
        edges.append(
            {
                "source": "milestone",
                "target": artifact_id,
                "type": "produces",
            }
        )

    graph = {"nodes": nodes, "edges": edges}
    tmp_path = out_path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        tmp_path.replace(out_path)
    except OSError as exc:
        raise RoadmapPlannerError(f"Failed to write plan graph: {exc}") from exc


def main() -> None:
    """Entry point for the roadmap planner.

    Reads the contract, generates sub‑goals, writes outputs, and logs progress.
    """
    # Configure a simple console logger.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    # Resolve paths relative to the repository root.
    repo_root = Path(__file__).resolve().parent.parent.parent  # .agentic-pi/runtime/..
    contract_path = repo_root / ".agentic-runs" / "roadmap" / "goal_contract.json"
    milestone_path = Path(__file__).with_name("milestone_plan.json")
    graph_path = Path(__file__).with_name("plan_graph.json")

    persistence = GoalPersistence(base_dir=repo_root)

    try:
        logger.info("Loading goal contract from %s", contract_path)
        contract = load_goal_contract(contract_path)
        persistence.update_phase("decomposing")
        subgoals = decompose_goal(contract)
        logger.info("Generated %d sub‑goals", len(subgoals))

        logger.info("Writing milestone plan to %s", milestone_path)
        write_milestone_plan(subgoals, milestone_path)

        logger.info("Writing plan graph to %s", graph_path)
        write_plan_graph(subgoals, graph_path)

        # Optional validation – uncomment if you want to enforce schema compliance.
        # errors = validate_milestone_plan(str(graph_path))
        # if errors:
        #     raise RoadmapPlannerError(f"Plan graph validation failed: {errors}")

        persistence.update_phase("completed")
        logger.info("Roadmap planner finished successfully.")
    except RoadmapPlannerError as exc:
        logger.error("Roadmap planner failed: %s", exc)
        persistence.update_phase("failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
