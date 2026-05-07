import argparse
import importlib.util
import json
import sys
from pathlib import Path


CERTIFYING_LEVELS = {"P2", "P3"}
STATUS_FILES = {"final_status.md", "certification.json", "policy_decision.json"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def requirement_is_certifying(text: str) -> bool:
    upper = text.upper()
    return ("P2" in upper or "P3" in upper) and "CERTIFYING" in upper


def branch_certifiability(candidate: dict):
    requirements = candidate.get("verifier_requirements", [])
    combined = " ".join(requirements)
    if requirement_is_certifying(combined):
        return True, "branch declares path to P2/P3 certifying verifier evidence"
    return False, "branch lacks path to P2/P3 certifying verifier evidence"


def status_artifacts_absent(run_dir: Path):
    return not any((run_dir / name).exists() for name in STATUS_FILES)


def select_branch(run_dir: Path):
    branch_generator = load_module(
        "branch_generator_for_selector",
        repo_root() / ".agentic-pi" / "runtime" / "branch_generator.py",
    )
    validation_errors = branch_generator.validate_branch_set(run_dir)
    manifest = load_json(run_dir / "branch_manifest.json")
    rejected = []
    selector_checks = []

    if validation_errors:
        decision = {
            "run_id": manifest.get("run_id", ""),
            "decision_status": "NO_CERTIFIABLE_BRANCH",
            "selected_branch": "",
            "reason": "Branch set failed validation.",
            "rejected_branches": [
                {"branch_id": "branch_set", "reason": "; ".join(validation_errors)}
            ],
            "selector_checks": ["branch validation failed"],
        }
        write_decision_files(run_dir, decision)
        return decision

    selector_checks.append("branch set validates")
    candidates = []
    for row in manifest["branches"]:
        candidate = load_json(run_dir / row["branch_candidate_path"])
        certifiable, reason = branch_certifiability(candidate)
        if certifiable:
            candidates.append(candidate)
            selector_checks.append(f"{candidate['branch_id']} has certifying verifier path")
        else:
            rejected.append({"branch_id": candidate["branch_id"], "reason": reason})

    if not candidates:
        decision = {
            "run_id": manifest["run_id"],
            "decision_status": "NEED_USER_VERIFIER",
            "selected_branch": "",
            "reason": "No branch declares a path to P2/P3 certifying verifier evidence.",
            "rejected_branches": rejected,
            "selector_checks": selector_checks,
        }
        write_decision_files(run_dir, decision)
        return decision

    selected = sorted(candidates, key=lambda item: (len(item.get("known_risks", [])), item["branch_id"]))[0]
    for candidate in candidates:
        if candidate["branch_id"] != selected["branch_id"]:
            rejected.append(
                {
                    "branch_id": candidate["branch_id"],
                    "reason": "not selected; another branch has equal certifiability and lower lexical/risk order"
                }
            )

    decision = {
        "run_id": manifest["run_id"],
        "decision_status": "SELECTED",
        "selected_branch": selected["branch_id"],
        "reason": "Selected branch has an explicit path to P2/P3 certifying verifier evidence.",
        "rejected_branches": rejected,
        "selector_checks": selector_checks + ["selector did not write certification status artifacts"],
    }
    write_decision_files(run_dir, decision)
    return decision


def write_decision_files(run_dir: Path, decision: dict):
    write_json(run_dir / "branch_decision.json", decision)
    if decision["selected_branch"]:
        write_json(
            run_dir / "selected_branch.json",
            {
                "run_id": decision["run_id"],
                "selected_branch": decision["selected_branch"],
                "reason": decision["reason"],
            },
        )
    write_json(
        run_dir / "rejected_branches.json",
        {
            "run_id": decision["run_id"],
            "rejected_branches": decision["rejected_branches"],
        },
    )
    write_json(
        run_dir / "selector_audit.json",
        {
            "run_id": decision["run_id"],
            "selector_checks": decision["selector_checks"],
            "status_artifacts_absent": status_artifacts_absent(run_dir),
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Select a branch by verifier-provenance evidence path.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)

    decision = select_branch(Path(args.run_dir))
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0 if decision["decision_status"] == "SELECTED" else 1


if __name__ == "__main__":
    sys.exit(main())
