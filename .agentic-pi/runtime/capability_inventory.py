#!/usr/bin/env python3
"""Write a deterministic local capability inventory for strategy planning."""
import argparse
import json
import sys
from pathlib import Path


CAPABILITIES = [
    {
        "capability_id": "file_write_run_folder",
        "description": "Guarded Worker can write approved files inside the run folder.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": True,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
    {
        "capability_id": "python_command",
        "description": "Run local Python commands through deterministic harness tools.",
        "allowed_for_task_types": ["coding", "debugging", "benchmark", "experiment"],
        "writes_run_folder": False,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "MEDIUM",
    },
    {
        "capability_id": "artifact_test",
        "description": "Execute goal_contract artifact tests for behavior evidence.",
        "allowed_for_task_types": ["coding", "debugging", "benchmark", "experiment"],
        "writes_run_folder": False,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
    {
        "capability_id": "plan_graph",
        "description": "Build artifact-linked plan_graph, artifact_registry, and task_graph files.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": True,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
    {
        "capability_id": "policy_engine",
        "description": "Policy engine decides provenance-mode status through certifier-owned path.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": True,
        "writes_status_artifacts": True,
        "certifier_owned": True,
        "requires_verifier_contract": True,
        "risk_level": "LOW",
    },
    {
        "capability_id": "audit",
        "description": "Audit run-folder evidence and block certification when invalid.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": True,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
    {
        "capability_id": "replay",
        "description": "Replay run-folder evidence read-only.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": True,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
    {
        "capability_id": "rollback_dry_run",
        "description": "Dry-run rollback for run-folder-owned artifacts.",
        "allowed_for_task_types": ["coding", "debugging", "benchmark", "experiment"],
        "writes_run_folder": True,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "MEDIUM",
    },
    {
        "capability_id": "pi_status_report",
        "description": "Pi may report status artifacts but cannot certify DONE.",
        "allowed_for_task_types": ["*"],
        "writes_run_folder": False,
        "writes_status_artifacts": False,
        "certifier_owned": False,
        "requires_verifier_contract": False,
        "risk_level": "LOW",
    },
]


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def inventory_for_run(run_dir: Path) -> dict:
    run_id = run_dir.name
    inventory = {
        "run_id": run_id,
        "capabilities": CAPABILITIES,
        "notes": [
            "Static deterministic local capability inventory.",
            "Strategy artifacts cannot use certifier-owned capabilities to self-certify.",
        ],
    }
    write_json(run_dir / "capability_inventory.json", inventory)
    return inventory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write deterministic local capability inventory.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        inventory = inventory_for_run(Path(args.run_dir))
    except Exception as exc:
        print(f"CAPABILITY_INVENTORY_FAILED: {exc}")
        return 1
    print(json.dumps(inventory, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
