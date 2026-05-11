#!/usr/bin/env python3
"""
Post-agent file verification.

After each Pi subagent completes, this script verifies that expected output
files actually exist on disk. Pi's write tool sometimes reports success but
the file never lands (known infrastructure issue).

If files are missing, it writes a diagnostic report and exits non-zero.
It never creates replacement artifacts.

Usage:
    python verify_agent_outputs.py <run_dir> <agent_name> <file1> [file2 ...]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    if len(sys.argv) < 4:
        print("Usage: python verify_agent_outputs.py <run_dir> <agent_name> <file1> [file2 ...]")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    agent_name = sys.argv[2]
    expected_files = sys.argv[3:]

    missing = []
    for f in expected_files:
        path = run_dir / f
        if path.exists():
            print(f"  OK: {f}")
        else:
            missing.append(f)
            print(f"  MISSING: {f} (write tool lost it)")

    if not missing:
        print(f"  All {len(expected_files)} files verified for {agent_name}")
        sys.exit(0)

    # Write diagnostic report for any missing files
    diagnostic = {
        "diagnostic_id": f"D.WRITE_LOSS.{run_dir.name}.{agent_name}",
        "trigger": f"Agent {agent_name} reported writing files that don't exist on disk",
        "root_cause": "Pi write tool returned success but file(s) not persisted",
        "missing_files": missing,
        "evidence": [f"{run_dir}/{f} does not exist" for f in missing],
        "recommended_action": "recreate_artifact",
        "severity": "warning",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    diag_dir = run_dir / "diagnostics"
    diag_dir.mkdir(exist_ok=True)
    diag_path = diag_dir / f"write_loss_{agent_name}.json"
    diag_path.write_text(json.dumps(diagnostic, indent=2))
    print(f"  Diagnostic written: {diag_path}")
    print(f"  WARNING: {len(missing)} file(s) lost by write tool")
    sys.exit(1)


if __name__ == "__main__":
    main()
