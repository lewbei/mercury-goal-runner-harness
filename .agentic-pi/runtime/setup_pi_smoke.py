import argparse
import hashlib
import json
import shutil
import sys
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


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_source(source_dir: Path):
    hashes = {}
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(source_dir).as_posix())] = file_hash(path)
    return hashes


def ensure_safe_target(run_root: Path, target_dir: Path):
    resolved_run_root = run_root.resolve()
    resolved_target = target_dir.resolve()
    if not str(resolved_target).startswith(str(resolved_run_root)):
        raise ValueError(f"target escapes run root: {target_dir}")
    if not target_dir.name.startswith("pi_smoke_"):
        raise ValueError("target run id must start with pi_smoke_")


def rewrite_json_run_id(path: Path, run_id: str):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and "run_id" in data:
        data["run_id"] = run_id
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rewrite_jsonl_run_id(path: Path, source_run_id: str, target_run_id: str):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            rewritten.append(line.replace(source_run_id, target_run_id))
            continue
        rendered = json.dumps(data, ensure_ascii=False)
        rewritten.append(rendered.replace(source_run_id, target_run_id))
    path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def rewrite_run_ids(target_dir: Path, source_run_id: str, target_run_id: str):
    for path in sorted(target_dir.rglob("*.json")):
        rewrite_json_run_id(path, target_run_id)
        text = path.read_text(encoding="utf-8")
        if source_run_id in text:
            path.write_text(text.replace(source_run_id, target_run_id), encoding="utf-8")

    for path in sorted(target_dir.rglob("*.jsonl")):
        rewrite_jsonl_run_id(path, source_run_id, target_run_id)


def remove_certifier_outputs(target_dir: Path):
    removed = []
    for rel_path in CERTIFIER_OUTPUTS:
        path = target_dir / rel_path
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(rel_path)
    return removed


def setup_pi_smoke(source_dir: Path, target_run_id: str, clean: bool = False):
    root = repo_root()
    run_root = root / ".agentic-runs"
    source_dir = source_dir.resolve()
    target_dir = run_root / target_run_id

    if not source_dir.is_dir():
        raise FileNotFoundError(f"source run folder not found: {source_dir}")
    ensure_safe_target(run_root, target_dir)

    before_hashes = snapshot_source(source_dir)

    if target_dir.exists():
        if not clean:
            raise FileExistsError(f"target exists; pass --clean to recreate: {target_dir}")
        shutil.rmtree(target_dir)

    shutil.copytree(source_dir, target_dir)
    source_goal = json.loads((source_dir / "goal_contract.json").read_text(encoding="utf-8-sig"))
    source_run_id = source_goal["run_id"]
    rewrite_run_ids(target_dir, source_run_id, target_run_id)
    removed = remove_certifier_outputs(target_dir)

    after_hashes = snapshot_source(source_dir)
    source_unchanged = before_hashes == after_hashes
    if not source_unchanged:
        raise RuntimeError("source run folder changed during disposable setup")

    report = {
        "status": "PASS",
        "target_run_id": target_run_id,
        "source_dir": str(source_dir),
        "target_dir": str(target_dir),
        "source_run_id": source_run_id,
        "removed_certifier_outputs": removed,
        "source_file_count": len(before_hashes),
        "source_unchanged": source_unchanged,
        "next_certifier_command": f"python .agentic-pi/validators/certify_run.py .agentic-runs/{target_run_id}",
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare a disposable pi_smoke_* run folder.")
    parser.add_argument(
        "--source",
        default=".agentic-pi/diagnostics/evaluation/cases/p2_strong",
        help="Copy-ready diagnostic source run folder.",
    )
    parser.add_argument("--target-run-id", required=True)
    parser.add_argument("--clean", action="store_true", help="Remove existing target first.")
    parser.add_argument("--output", help="Optional setup report path.")
    args = parser.parse_args(argv)

    source = (repo_root() / args.source).resolve()
    report = setup_pi_smoke(source, args.target_run_id, args.clean)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"SETUP_PI_SMOKE_FAILED: {exc}")
        sys.exit(1)
