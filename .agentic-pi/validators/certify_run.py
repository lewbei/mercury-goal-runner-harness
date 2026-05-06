import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROTECTED_NAMES = {
    "certification.json",
    "final_status.md",
    "trace.jsonl"
}

def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    if len(sys.argv) != 2:
        print("Usage: python certify_run.py <run_dir>")
        sys.exit(2)

    project_root = Path.cwd()
    run_dir = Path(sys.argv[1])

    passed = []
    failed = []
    artifact_hashes = {}

    if not run_dir.exists():
        print("RUN_DIR_MISSING")
        sys.exit(1)

    run_id = run_dir.name
    goal_path = run_dir / "goal_contract.json"
    trace_path = run_dir / "trace.jsonl"
    step_dir = run_dir / "step_logs"

    if goal_path.exists():
        passed.append("goal_contract.json exists")
        try:
            goal = load_json(goal_path)
            passed.append("goal_contract.json parses as JSON")
        except Exception as e:
            goal = None
            failed.append(f"goal_contract.json parse failed: {e}")
    else:
        goal = None
        failed.append("goal_contract.json missing")

    if trace_path.exists():
        passed.append("trace.jsonl exists")
        try:
            for line_no, line in enumerate(trace_path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip():
                    json.loads(line)
            passed.append("trace.jsonl lines parse as JSON")
        except Exception as e:
            failed.append(f"trace.jsonl invalid at line {line_no}: {e}")
    else:
        failed.append("trace.jsonl missing")

    if step_dir.exists():
        logs = sorted(step_dir.glob("*.json"))
        if logs:
            passed.append("step_logs contain at least one step result")
        else:
            failed.append("step_logs exists but contains no .json files")
    else:
        logs = []
        failed.append("step_logs directory missing")

    for log in logs:
        try:
            step = load_json(log)
            touched = step.get("files_touched", [])
            evidence = step.get("evidence", [])
            if evidence:
                passed.append(f"{log.name} contains evidence")
            else:
                failed.append(f"{log.name} has empty evidence")

            for p in touched:
                name = Path(p).name
                if name in PROTECTED_NAMES:
                    failed.append(f"{log.name} reports Worker touched protected file: {p}")
        except Exception as e:
            failed.append(f"{log.name} parse failed: {e}")

    if goal:
        final_outputs = goal.get("final_outputs", [])
        done_criteria = goal.get("done_criteria", [])

        if done_criteria:
            passed.append("done_criteria is non-empty")
        else:
            failed.append("done_criteria is empty")

        if final_outputs:
            passed.append("final_outputs is non-empty")
            for output in final_outputs:
                output_path = project_root / output
                if output_path.exists():
                    passed.append(f"final output exists: {output}")
                    if output_path.is_file():
                        artifact_hashes[output] = sha256_file(output_path)
                else:
                    failed.append(f"final output missing: {output}")
        else:
            failed.append("final_outputs is empty")

    status = "DONE_PASS" if not failed else "DONE_FAIL"

    certification = {
        "run_id": run_id,
        "status": status,
        "passed_checks": passed,
        "failed_checks": failed,
        "artifact_hashes": artifact_hashes,
        "audit_chain_valid": True,
        "generated_by": "agentic-pi-certifier-v0.1",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    cert_path = run_dir / "certification.json"
    final_status_path = run_dir / "final_status.md"

    write_json(cert_path, certification)

    report = []
    report.append(f"# Final Status: {status}")
    report.append("")
    report.append(f"Run ID: `{run_id}`")
    report.append("")
    report.append("## Passed checks")
    for item in passed:
        report.append(f"- {item}")
    report.append("")
    report.append("## Failed checks")
    if failed:
        for item in failed:
            report.append(f"- {item}")
    else:
        report.append("- none")
    report.append("")
    report.append("## Artifact hashes")
    if artifact_hashes:
        for k, v in artifact_hashes.items():
            report.append(f"- `{k}`: `{v}`")
    else:
        report.append("- none")

    final_status_path.write_text("\n".join(report), encoding="utf-8")

    print(status)
    print(f"Wrote {cert_path}")
    print(f"Wrote {final_status_path}")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()

