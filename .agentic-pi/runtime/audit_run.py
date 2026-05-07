import argparse
import hashlib
import json
import sys
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_trace(trace_path: Path):
    count = 0
    for line in trace_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        json.loads(line)
        count += 1
    return count


def status_from_final_status(path: Path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    return first.removeprefix("# Final Status: ").strip()


def collect_status_artifacts(run_dir: Path):
    statuses = {}
    artifacts = []
    for name in ["certification.json", "policy_decision.json"]:
        path = run_dir / name
        if path.is_file():
            status = load_json(path).get("status", "")
            statuses[name] = status
            artifacts.append({"path": name, "status": status})
    final_status_path = run_dir / "final_status.md"
    if final_status_path.is_file():
        status = status_from_final_status(final_status_path)
        statuses["final_status.md"] = status
        artifacts.append({"path": "final_status.md", "status": status})
    return statuses, artifacts


def audit_run(run_dir: Path):
    violations = []
    checks = []
    artifact_hashes = []
    goal_path = run_dir / "goal_contract.json"
    goal_contract_present = goal_path.is_file()
    trace_event_count = 0
    step_log_count = 0

    if goal_contract_present:
        goal = load_json(goal_path)
        run_id = goal.get("run_id", run_dir.name)
        checks.append("goal_contract.json exists")
        for rel_path in goal.get("final_outputs", []):
            path = run_dir / rel_path
            if path.is_file():
                artifact_hashes.append({"path": rel_path, "sha256": sha256_file(path)})
                checks.append(f"final output hash recorded: {rel_path}")
            else:
                violations.append(f"final output missing during audit: {rel_path}")
    else:
        run_id = run_dir.name
        violations.append("goal_contract.json missing")

    trace_path = run_dir / "trace.jsonl"
    if trace_path.is_file():
        try:
            trace_event_count = parse_trace(trace_path)
            checks.append(f"trace.jsonl parses with {trace_event_count} event(s)")
        except Exception as exc:
            violations.append(f"trace.jsonl invalid: {exc}")
    else:
        violations.append("trace.jsonl missing")

    step_logs = sorted((run_dir / "step_logs").glob("*.json")) if (run_dir / "step_logs").is_dir() else []
    step_log_count = len(step_logs)
    if step_logs:
        checks.append(f"step_logs contain {len(step_logs)} file(s)")
    else:
        violations.append("step_logs missing or empty")

    statuses, status_artifacts = collect_status_artifacts(run_dir)
    if statuses:
        non_empty = {value for value in statuses.values() if value}
        if len(non_empty) > 1:
            violations.append(f"status artifacts disagree: {statuses}")
        else:
            checks.append("status artifacts agree")

    manifest = {
        "run_id": run_id,
        "provenance_mode": (run_dir / "verifier_contract.json").is_file(),
        "goal_contract_present": goal_contract_present,
        "trace_event_count": trace_event_count,
        "step_log_count": step_log_count,
        "status_artifacts": status_artifacts,
        "artifact_hashes": artifact_hashes,
    }
    write_json(run_dir / "run_manifest.json", manifest)
    checks.append("run_manifest.json written")

    report = {
        "run_id": run_id,
        "valid": not violations,
        "checks": checks,
        "violations": violations,
        "artifact_hashes": artifact_hashes,
    }
    write_json(run_dir / "audit_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit a run folder without certifying DONE.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    report = audit_run(Path(args.run_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
