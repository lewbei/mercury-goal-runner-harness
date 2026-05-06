#!/usr/bin/env python3
"""Rollback a file change for a given run.

Usage:
    python .agentic-pi/runtime/rollback.py --run-id <run_id> --file <relative_path>

The script expects a backup copy of the file under:
    .agentic-runs/<run_id>/backups/<relative_path>
If the backup exists, it will be copied over the original file.
"""
import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Rollback a file change for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--file", required=True, help="Relative path to the file to rollback")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    backup_path = run_dir / "backups" / args.file
    target_path = Path(args.file)
    if not backup_path.is_file():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    # Ensure target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(backup_path, target_path)
    print(f"Rolled back {target_path} from backup {backup_path}")

if __name__ == "__main__":
    main()
