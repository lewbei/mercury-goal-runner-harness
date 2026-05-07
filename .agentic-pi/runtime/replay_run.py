import argparse
import hashlib
import json
import sys
from pathlib import Path


def load_json(path):
    if not path.is_file():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def resolve_run_file(run_dir: Path, rel_path: str):
    target = Path(rel_path)
    if target.is_absolute():
        raise ValueError("manifest artifact path is absolute")
    root = run_dir.resolve()
    resolved = (root / target).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("manifest artifact path escapes run folder")
    return resolved

def verify_manifest(run_dir: Path, trace_event_count: int, step_log_count: int, provenance_mode: bool, violations: list):
    manifest_path = run_dir / "run_manifest.json"
    checks = []
    if not manifest_path.is_file():
        return False, checks
    manifest = load_json(manifest_path) or {}
    if manifest.get("trace_event_count") != trace_event_count:
        violations.append("run_manifest trace_event_count mismatch")
    if manifest.get("step_log_count") != step_log_count:
        violations.append("run_manifest step_log_count mismatch")
    if manifest.get("provenance_mode") != provenance_mode:
        violations.append("run_manifest provenance_mode mismatch")
    for item in manifest.get("artifact_hashes", []):
        rel_path = item.get("path", "")
        expected_hash = item.get("sha256", "")
        try:
            path = resolve_run_file(run_dir, rel_path)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        if not path.is_file():
            violations.append(f"manifest artifact missing: {rel_path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            violations.append(f"manifest hash mismatch: {rel_path}")
        else:
            checks.append(f"hash ok: {rel_path}")
    return True, checks

def replay_run(run_dir: Path):
    violations = []
    goal_contract_present = (run_dir / "goal_contract.json").is_file()
    if not goal_contract_present:
        violations.append("goal_contract.json missing")

    trace_event_count = 0
    trace_path = run_dir / "trace.jsonl"
    if trace_path.is_file():
        try:
            for line in trace_path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    json.loads(line)
                    trace_event_count += 1
        except Exception as exc:
            violations.append(f"trace.jsonl invalid: {exc}")
    else:
        violations.append("trace.jsonl missing")

    step_log_dir = run_dir / "step_logs"
    step_log_count = len(sorted(step_log_dir.glob("*.json"))) if step_log_dir.is_dir() else 0
    if step_log_count == 0:
        violations.append("step_logs missing or empty")

    certification = load_json(run_dir / "certification.json") or {}
    policy = load_json(run_dir / "policy_decision.json") or {}
    provenance_mode = (run_dir / "verifier_contract.json").is_file()
    manifest_present, manifest_hash_checks = verify_manifest(
        run_dir,
        trace_event_count,
        step_log_count,
        provenance_mode,
        violations,
    )
    report = {
        "run_id": (load_json(run_dir / "goal_contract.json") or {}).get("run_id", run_dir.name),
        "valid": not violations,
        "goal_contract_present": goal_contract_present,
        "trace_event_count": trace_event_count,
        "step_log_count": step_log_count,
        "provenance_mode": provenance_mode,
        "manifest_present": manifest_present,
        "manifest_hash_checks": manifest_hash_checks,
        "certification_status": certification.get("status", ""),
        "policy_status": policy.get("status", ""),
        "violations": violations,
    }
    write_json(run_dir / "replay_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description="Replay a run and write replay_report.json")
    parser.add_argument("--run-id", help="Run identifier under .agentic-runs")
    parser.add_argument("run_dir", nargs="?", help="Explicit run folder")
    args = parser.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else Path(".agentic-runs") / args.run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")
    report = replay_run(run_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1

if __name__ == "__main__":
    sys.exit(main())
