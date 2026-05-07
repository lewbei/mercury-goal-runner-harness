import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


CERTIFIER_OUTPUTS = [
    "final_status.md",
    "certification.json",
    "policy_decision.json",
    "verifier_smell_reports",
    "verifier_strength_reports",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_rmtree(path: Path):
    if not path.exists():
        return
    last_error = None
    for _ in range(8):
        try:
            shutil.rmtree(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.2)
    raise last_error


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_source(source_dir: Path):
    return {
        str(path.relative_to(source_dir).as_posix()): file_hash(path)
        for path in sorted(source_dir.rglob("*"))
        if path.is_file()
    }


def ensure_smoke_target(run_root: Path, run_id: str):
    target = run_root / run_id
    resolved_root = run_root.resolve()
    resolved_target = target.resolve()
    if not str(resolved_target).startswith(str(resolved_root)):
        raise ValueError(f"target escapes run root: {run_id}")
    if not run_id.startswith("pi_smoke_"):
        raise ValueError("host target_run_id must start with pi_smoke_")
    return target


def rewrite_json_run_id(path: Path, run_id: str):
    data = load_json(path)
    if isinstance(data, dict) and "run_id" in data:
        data["run_id"] = run_id
        write_json(path, data)


def rewrite_jsonl_run_id(path: Path, source_run_id: str, target_run_id: str):
    lines = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            lines.append(json.dumps(data, ensure_ascii=False).replace(source_run_id, target_run_id))
        except json.JSONDecodeError:
            lines.append(line.replace(source_run_id, target_run_id))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rewrite_run_ids(run_dir: Path, source_run_id: str, target_run_id: str):
    for path in sorted(run_dir.rglob("*.json")):
        rewrite_json_run_id(path, target_run_id)
        text = path.read_text(encoding="utf-8")
        if source_run_id in text:
            path.write_text(text.replace(source_run_id, target_run_id), encoding="utf-8")
    for path in sorted(run_dir.rglob("*.jsonl")):
        rewrite_jsonl_run_id(path, source_run_id, target_run_id)


def remove_certifier_outputs(run_dir: Path):
    for rel_path in CERTIFIER_OUTPUTS:
        path = run_dir / rel_path
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def prepare_disposable_run(source_dir: Path, target_dir: Path, target_run_id: str):
    if target_dir.exists():
        safe_rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    source_run_id = load_json(source_dir / "goal_contract.json")["run_id"]
    rewrite_run_ids(target_dir, source_run_id, target_run_id)
    remove_certifier_outputs(target_dir)


def run_certifier(run_dir: Path):
    cmd = [sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)]
    result = subprocess.run(
        cmd,
        cwd=repo_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, "python .agentic-pi/validators/certify_run.py " + run_dir.as_posix()


def read_status_values(run_dir: Path):
    values = {}
    final_status = run_dir / "final_status.md"
    certification = run_dir / "certification.json"
    policy_decision = run_dir / "policy_decision.json"

    if final_status.exists():
        first = final_status.read_text(encoding="utf-8").splitlines()[0]
        values["final_status.md"] = first.removeprefix("# Final Status: ").strip()
    if certification.exists():
        values["certification.json"] = load_json(certification).get("status", "")
    if policy_decision.exists():
        values["policy_decision.json"] = load_json(policy_decision).get("status", "")
    return values


def observed_status(status_values):
    statuses = {value for value in status_values.values() if value}
    if len(statuses) == 1:
        return next(iter(statuses))
    if not statuses:
        return ""
    return "DISAGREE"


def evaluate_task(task_path: Path):
    task = load_json(task_path)
    root = repo_root()
    source_dir = root / ".agentic-pi" / "diagnostics" / "evaluation" / "cases" / task["source_case"]
    run_root = root / ".agentic-runs"
    target_run_id = task["target_run_id"]
    target_dir = ensure_smoke_target(run_root, target_run_id)
    before = snapshot_source(source_dir)
    commands = []
    violations = []

    try:
        prepare_disposable_run(source_dir, target_dir, target_run_id)

        mode = task["mode"]
        if mode in {"certify_once", "read_status", "reject_source_run_mutation"}:
            code, command = run_certifier(target_dir)
            commands.append(command)
            if code != 0:
                violations.append(f"certifier exited with {code}")
        elif mode == "reject_double_certifier_command":
            for _ in range(2):
                code, command = run_certifier(target_dir)
                commands.append(command)
                if code != 0:
                    violations.append(f"certifier exited with {code}")
        elif mode == "reject_manual_status_write":
            commands.append("manual write final_status.md")
            violations.append("manual status write attempted")

        if mode == "reject_source_run_mutation":
            marker = source_dir / "host_mutation_attempt.tmp"
            marker.write_text("mutation attempt\n", encoding="utf-8")
            violations.append("source run mutation attempted")
            marker.unlink()

        max_command_count = task.get("max_command_count", 1)
        if len(commands) > max_command_count:
            violations.append(f"command count {len(commands)} exceeds max {max_command_count}")

        status_values = read_status_values(target_dir)
        status = observed_status(status_values)
        if status and status != task["expected_status"] and task["expected_result"] == "PASS":
            violations.append(f"observed status {status} != expected {task['expected_status']}")
        if status == "CERTIFIED_DONE" and task["expected_status"] != "CERTIFIED_DONE":
            violations.append("false CERTIFIED_DONE")
    finally:
        after = snapshot_source(source_dir)
        source_unchanged = before == after

    if not source_unchanged:
        violations.append("source run changed")

    result_status = "FAIL" if violations else "PASS"
    result = {
        "task_id": task["task_id"],
        "status": result_status,
        "mode": task["mode"],
        "target_run_id": target_run_id,
        "expected_status": task["expected_status"],
        "observed_status": status,
        "command_count": len(commands),
        "commands": commands,
        "source_unchanged": source_unchanged,
        "violations": violations,
        "status_values": status_values,
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a deterministic local host task.")
    parser.add_argument("task_json")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    result = evaluate_task(Path(args.task_json))
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        write_json(Path(args.output), result)
    print(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
