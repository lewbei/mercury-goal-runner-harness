#!/usr/bin/env python3
"""Record prompt compiler provenance for a run.

This artifact is provenance-only. It records how a raw prompt became the
`execution_prompt` in goal_contract.json. It cannot certify DONE and must not be
used as verifier evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_PROMPT = ROOT / ".pi" / "agents" / "prompt-compiler.md"
DEFAULT_RUNTIME_PROMPT = ROOT / ".agentic-pi" / "prompts" / "prompt_compiler.md"
ARTIFACT_NAME = "prompt_compiler.prompt.json"
SCHEMA_VERSION = "prompt_provenance_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_run_dir(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        if path.parts and path.parts[0] == ".agentic-runs":
            path = ROOT / path
        elif (ROOT / ".agentic-runs" / path).exists():
            path = ROOT / ".agentic-runs" / path
        else:
            path = ROOT / path
    path = path.resolve()
    runs_root = (ROOT / ".agentic-runs").resolve()
    if path != runs_root and runs_root not in path.parents:
        raise ValueError(f"run path must be under .agentic-runs: {raw}")
    return path


def prompt_file_entry(path: Path) -> dict:
    return {
        "path": run_relative(path),
        "exists": path.is_file(),
        "sha256": sha256_file(path),
    }


def build_prompt_provenance(
    run_dir: Path,
    *,
    source_agent: str = "prompt-compiler",
    source_model: str = "unknown",
    source_phase: str = "intake_prompt_compilation",
) -> dict:
    goal_path = run_dir / "goal_contract.json"
    if not goal_path.is_file():
        raise FileNotFoundError(f"goal_contract.json not found: {goal_path}")

    contract = load_json(goal_path)
    if not isinstance(contract, dict):
        raise ValueError("goal_contract.json must contain a JSON object")

    run_id = str(contract.get("run_id") or run_dir.name)
    if run_id != run_dir.name:
        raise ValueError(f"goal_contract.run_id {run_id!r} does not match run folder {run_dir.name!r}")

    raw_prompt = str(contract.get("raw_user_prompt") or "")
    execution_prompt = str(contract.get("execution_prompt") or "")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "PROMPT.PROVENANCE.PROMPT_COMPILER",
        "run_id": run_id,
        "created_at": utc_now(),
        "source": {
            "tool": "prompt_provenance.py",
            "agent": source_agent,
            "model": source_model,
            "source_phase": source_phase,
        },
        "authority": {
            "authority_level": "provenance_only",
            "can_certify_done": False,
            "not_evidence_for_done": True,
            "notes": "Records prompt transformation only; policy_engine.py/certify_run.py own final status.",
        },
        "goal_contract": {
            "path": "goal_contract.json",
            "sha256": sha256_file(goal_path),
        },
        "prompt_compiler_files": {
            "agent_prompt": prompt_file_entry(DEFAULT_AGENT_PROMPT),
            "runtime_prompt": prompt_file_entry(DEFAULT_RUNTIME_PROMPT),
        },
        "raw_prompt": {
            "text": raw_prompt,
            "sha256": sha256_text(raw_prompt),
            "length_chars": len(raw_prompt),
            "present": bool(raw_prompt.strip()),
        },
        "execution_prompt": {
            "text": execution_prompt,
            "sha256": sha256_text(execution_prompt),
            "length_chars": len(execution_prompt),
            "present": bool(execution_prompt.strip()),
        },
        "checks": {
            "goal_contract_json_valid": True,
            "raw_prompt_present": bool(raw_prompt.strip()),
            "execution_prompt_present": bool(execution_prompt.strip()),
            "authority_files_written": False,
        },
    }


def record_prompt_provenance(
    run_dir: Path,
    *,
    source_agent: str = "prompt-compiler",
    source_model: str = "unknown",
    source_phase: str = "intake_prompt_compilation",
) -> Path:
    artifact = build_prompt_provenance(
        run_dir,
        source_agent=source_agent,
        source_model=source_model,
        source_phase=source_phase,
    )
    out_path = run_dir / "prompt_provenance" / ARTIFACT_NAME
    write_json(out_path, artifact)
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Record prompt compiler provenance for a run")
    parser.add_argument("run", help="Run id or .agentic-runs/<run_id> path")
    parser.add_argument("--source-agent", default="prompt-compiler")
    parser.add_argument("--source-model", default="unknown")
    parser.add_argument("--source-phase", default="intake_prompt_compilation")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run)
        out_path = record_prompt_provenance(
            run_dir,
            source_agent=args.source_agent,
            source_model=args.source_model,
            source_phase=args.source_phase,
        )
    except Exception as exc:
        print(f"PROMPT_PROVENANCE_FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"PROMPT_PROVENANCE_WRITTEN {run_relative(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
