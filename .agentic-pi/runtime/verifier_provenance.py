#!/usr/bin/env python3
"""Create runtime-stamped verifier provenance artifacts."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SOURCE_DEFAULTS = {
    "same_run_worker": {
        "provenance_level": "P0",
        "authority": "advisory",
        "same_worker_as_solution": True,
    },
    "same_run_verifier_agent": {
        "provenance_level": "P1",
        "authority": "gating",
        "same_worker_as_solution": False,
    },
    "independent_verifier_agent": {
        "provenance_level": "P2",
        "authority": "certifying",
        "same_worker_as_solution": False,
    },
    "existing_repo_test": {
        "provenance_level": "P1",
        "authority": "gating",
        "same_worker_as_solution": False,
    },
    "user_provided": {
        "provenance_level": "P3",
        "authority": "certifying",
        "same_worker_as_solution": False,
    },
    "hidden_oracle": {
        "provenance_level": "P3",
        "authority": "certifying",
        "same_worker_as_solution": False,
    },
    "external_benchmark": {
        "provenance_level": "P3",
        "authority": "certifying",
        "same_worker_as_solution": False,
    },
    "human_review": {
        "provenance_level": "P3",
        "authority": "certifying",
        "same_worker_as_solution": False,
    },
}


ARTIFACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def safe_artifact_filename(artifact_id: str) -> str:
    if not ARTIFACT_ID_PATTERN.match(artifact_id):
        raise ValueError(f"artifact_id contains unsafe characters: {artifact_id}")
    return f"{artifact_id}.json"


def bool_from_text(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean text, got {value!r}")


def create_verifier_artifact(
    run_dir: Path,
    artifact_id: str,
    target_artifact: str,
    kind: str,
    source: str,
    created_at_phase: str,
    author_agent: str,
    author_model: str,
    provenance_level: str = None,
    authority: str = None,
    same_worker_as_solution: bool = None,
    depends_on_solution: bool = None,
    executes_code: bool = True,
    assertion_count: int = 0,
    mock_ratio_percent: int = 0,
    smell_flags=None,
    created_at: str = None,
    solution_exists_at_creation: bool = None,
):
    defaults = SOURCE_DEFAULTS.get(source)
    if defaults is None:
        raise ValueError(f"unknown verifier source: {source}")

    target_path = resolve_run_path(run_dir, target_artifact)
    if solution_exists_at_creation is None:
        solution_exists = target_path.is_file()
    else:
        solution_exists = solution_exists_at_creation
    if same_worker_as_solution is None:
        same_worker_as_solution = defaults["same_worker_as_solution"]
    if depends_on_solution is None:
        depends_on_solution = created_at_phase in {"during_solution", "post_solution"} or solution_exists

    artifact = {
        "artifact_id": artifact_id,
        "run_id": run_dir.name,
        "target_artifact": target_artifact,
        "kind": kind,
        "source": source,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "created_at_phase": created_at_phase,
        "author_agent": author_agent,
        "author_model": author_model,
        "provenance_level": provenance_level or defaults["provenance_level"],
        "depends_on_solution": depends_on_solution,
        "same_worker_as_solution": same_worker_as_solution,
        "executes_code": executes_code,
        "assertion_count": assertion_count,
        "mock_ratio_percent": mock_ratio_percent,
        "smell_flags": smell_flags or [],
        "authority": authority or defaults["authority"],
        "solution_exists_at_creation": solution_exists,
    }

    verifier_dir = run_dir / "verifier_artifacts"
    verifier_dir.mkdir(parents=True, exist_ok=True)
    output_path = verifier_dir / safe_artifact_filename(artifact_id)
    write_json(output_path, artifact)
    return output_path, artifact


def main():
    parser = argparse.ArgumentParser(description="Create a verifier provenance artifact")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source", required=True, choices=sorted(SOURCE_DEFAULTS))
    parser.add_argument("--phase", required=True, dest="created_at_phase")
    parser.add_argument("--kind", required=True)
    parser.add_argument("--author-agent", default="certifier")
    parser.add_argument("--author-model", default="deterministic-runtime")
    parser.add_argument("--provenance-level")
    parser.add_argument("--authority")
    parser.add_argument("--same-worker-as-solution", type=bool_from_text)
    parser.add_argument("--depends-on-solution", type=bool_from_text)
    parser.add_argument("--executes-code", type=bool_from_text, default=True)
    parser.add_argument("--solution-exists-at-creation", type=bool_from_text)
    parser.add_argument("--assertion-count", type=int, default=0)
    parser.add_argument("--mock-ratio-percent", type=int, default=0)
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run folder missing: {run_dir}")

    output_path, _ = create_verifier_artifact(
        run_dir=run_dir,
        artifact_id=args.artifact_id,
        target_artifact=args.target,
        kind=args.kind,
        source=args.source,
        created_at_phase=args.created_at_phase,
        author_agent=args.author_agent,
        author_model=args.author_model,
        provenance_level=args.provenance_level,
        authority=args.authority,
        same_worker_as_solution=args.same_worker_as_solution,
        depends_on_solution=args.depends_on_solution,
        executes_code=args.executes_code,
        solution_exists_at_creation=args.solution_exists_at_creation,
        assertion_count=args.assertion_count,
        mock_ratio_percent=args.mock_ratio_percent,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
