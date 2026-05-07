import argparse
import hashlib
import json
import sys
from pathlib import Path


FORBIDDEN_STATUS_VALUES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_run_path(run_dir: Path, rel_path: str):
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute branch path is not allowed: {rel_path}")
    root = run_dir.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"branch path escapes run folder: {rel_path}")
    return resolved


def branch_roles(complexity: str):
    if complexity == "SIMPLE":
        return ["minimal"]
    if complexity == "MEDIUM":
        return ["minimal", "robust"]
    return ["minimal", "robust", "skeptic"]


def branch_id_for_role(role: str):
    return f"B.{role.upper()}"


def branch_plan(role: str):
    output_artifact = f"A.{role.upper()}.OUTPUT"
    output_path = f"branches/{branch_id_for_role(role)}/artifacts/output.txt"
    return {
        "artifact_id": output_artifact,
        "artifact_path": output_path,
        "verifier_requirements": [
            "target artifact must be verified by P2 or P3 evidence",
            "verifier strength must be certifying",
            "P0/P1 evidence is advisory only"
        ],
        "known_risks": [f"{role} planner is a candidate only and cannot certify DONE"],
    }


def write_branch_artifacts(run_dir: Path, goal_hash: str, role: str):
    branch_id = branch_id_for_role(role)
    branch_rel_dir = Path("branches") / branch_id
    branch_dir = run_dir / branch_rel_dir
    plan = branch_plan(role)
    artifact_id = plan["artifact_id"]
    artifact_path = plan["artifact_path"]
    task_id = f"T.{role.upper()}.WRITE_OUTPUT"

    plan_graph = {
        "nodes": [
            {
                "node_id": task_id,
                "type": "task",
                "task_id": task_id,
                "description": f"{role} candidate writes planned output"
            },
            {
                "node_id": artifact_id,
                "type": "artifact",
                "artifact_id": artifact_id,
                "path": artifact_path
            }
        ],
        "edges": [
            {
                "source": task_id,
                "target": artifact_id,
                "type": "produces"
            }
        ]
    }
    artifact_registry = {
        "artifacts": [
            {
                "artifact_id": artifact_id,
                "path": artifact_path,
                "producer_task": task_id,
                "required_by": [],
                "type": "text",
                "validation_status": "planned"
            }
        ]
    }
    task_graph = {
        "tasks": [
            {
                "task_id": task_id,
                "title": f"{role} candidate output task",
                "requires": [],
                "produces": [artifact_id],
                "pass_condition": [
                    f"{artifact_id} exists",
                    "P2/P3 verifier evidence is available before final certification"
                ],
                "description": "Candidate task only; not certifying evidence."
            }
        ],
        "dependencies": [
            {
                "from": task_id,
                "to": artifact_id,
                "type": "produces"
            }
        ]
    }

    candidate = {
        "branch_id": branch_id,
        "planner_id": f"planner-{role}",
        "planner_role": role,
        "goal_contract_hash": goal_hash,
        "plan_graph_path": (branch_rel_dir / "plan_graph.json").as_posix(),
        "artifact_registry_path": (branch_rel_dir / "artifact_registry.json").as_posix(),
        "task_graph_path": (branch_rel_dir / "task_graph.json").as_posix(),
        "verifier_requirements": plan["verifier_requirements"],
        "known_risks": plan["known_risks"],
        "selection_state": "candidate"
    }

    for rel_path, obj in [
        ("branch_candidate.json", candidate),
        ("plan_graph.json", plan_graph),
        ("artifact_registry.json", artifact_registry),
        ("task_graph.json", task_graph),
    ]:
        write_json(branch_dir / rel_path, obj)
    return candidate


def generate_branches(run_dir: Path):
    goal_path = run_dir / "goal_contract.json"
    goal = load_json(goal_path)
    goal_hash = file_hash(goal_path)
    branches = []
    for role in branch_roles(goal.get("complexity_level", "SIMPLE")):
        candidate = write_branch_artifacts(run_dir, goal_hash, role)
        branches.append(
            {
                "branch_id": candidate["branch_id"],
                "branch_candidate_path": f"branches/{candidate['branch_id']}/branch_candidate.json"
            }
        )

    manifest = {
        "run_id": goal["run_id"],
        "goal_contract_hash": goal_hash,
        "branches": branches,
        "generated_by": "branch-generator-v0.7"
    }
    write_json(run_dir / "branch_manifest.json", manifest)
    return manifest


def validate_branch_set(run_dir: Path):
    violations = []
    manifest_path = run_dir / "branch_manifest.json"
    if not manifest_path.is_file():
        return ["branch_manifest.json missing"]
    manifest = load_json(manifest_path)
    seen_branch_ids = set()

    for branch in manifest.get("branches", []):
        branch_id = branch.get("branch_id", "")
        if branch_id in seen_branch_ids:
            violations.append(f"duplicate branch_id: {branch_id}")
        seen_branch_ids.add(branch_id)
        candidate_rel = branch.get("branch_candidate_path", "")
        try:
            candidate_path = resolve_run_path(run_dir, candidate_rel)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        if not candidate_path.is_file():
            violations.append(f"branch candidate missing: {candidate_rel}")
            continue
        candidate = load_json(candidate_path)
        for key, value in candidate.items():
            if key.endswith("status") or key in {"status", "selection_state"}:
                if value in FORBIDDEN_STATUS_VALUES:
                    violations.append(f"branch {branch_id} claims forbidden final authority: {value}")
        if not candidate.get("verifier_requirements"):
            violations.append(f"branch {branch_id} missing verifier requirements")

        for path_key in ["plan_graph_path", "artifact_registry_path", "task_graph_path"]:
            rel_path = candidate.get(path_key, "")
            try:
                resolved = resolve_run_path(run_dir, rel_path)
            except ValueError as exc:
                violations.append(str(exc))
                continue
            if "verifier_artifacts" in rel_path.replace("\\", "/"):
                violations.append(f"branch {branch_id} touches verifier_artifacts: {rel_path}")
            if not resolved.is_file():
                violations.append(f"branch {branch_id} missing {path_key}: {rel_path}")

        registry_path = run_dir / candidate.get("artifact_registry_path", "")
        if registry_path.is_file():
            registry = load_json(registry_path)
            seen_artifacts = set()
            for artifact in registry.get("artifacts", []):
                artifact_id = artifact.get("artifact_id", "")
                if artifact_id in seen_artifacts:
                    violations.append(f"branch {branch_id} duplicate artifact_id: {artifact_id}")
                seen_artifacts.add(artifact_id)
                path = artifact.get("path", "")
                try:
                    resolve_run_path(run_dir, path)
                except ValueError as exc:
                    violations.append(str(exc))
                if "verifier_artifacts" in path.replace("\\", "/"):
                    violations.append(f"branch {branch_id} artifact touches verifier_artifacts: {path}")
    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate or validate deterministic branch candidates.")
    parser.add_argument("run_dir")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)

    if args.validate:
        violations = validate_branch_set(run_dir)
        if violations:
            for violation in violations:
                print(violation)
            return 1
        print("BRANCH_SET_VALID")
        return 0

    manifest = generate_branches(run_dir)
    print(f"Wrote {run_dir / 'branch_manifest.json'} with {len(manifest['branches'])} branch(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
