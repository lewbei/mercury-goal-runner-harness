import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RED_TEAM_PATH = ROOT / ".agentic-pi" / "runtime" / "red_team_loop.py"


def _load_red_team_loop():
    spec = importlib.util.spec_from_file_location("red_team_loop", RED_TEAM_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["red_team_loop"] = module
    spec.loader.exec_module(module)
    return module


def main():
    red_team_loop = _load_red_team_loop()
    result = red_team_loop.run_red_team(rounds=20, seed_runs=1)
    for row in result["results"]:
        label = "PASS" if row["passed"] else "FAIL"
        print(f"[{label}] {row['case_id']}: expected {row['expected_status']}, got {row['actual_status']}")
        if row["errors"] and not row["passed"]:
            print("  Errors:", row["errors"])

    metrics = result["metrics"]
    print(f"\nMeta-harness summary: {metrics['passed_count']}/{metrics['case_count']} passed ({metrics['regression_pass_rate']:.0%})")
    print(json.dumps({
        "false_certified_done_rate": metrics["false_certified_done_rate"],
        "monitor_miss_rate": metrics["monitor_miss_rate"],
        "policy_mismatch_escape_rate": metrics["policy_mismatch_escape_rate"],
        "false_block_rate": metrics["false_block_rate"],
    }, indent=2))

    if metrics["regression_pass_rate"] != 1.0:
        sys.exit(1)


if __name__ == "__main__":
    main()
