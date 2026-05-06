import json
import subprocess
import sys
from pathlib import Path
import shutil

def main():
    # Setup run directory
    run_id = "hard_test_001"
    base_dir = Path(".agentic-runs")
    run_dir = base_dir / run_id
    # Clean up if exists
    if run_dir.exists():
        shutil.rmtree(run_dir)
    # Create contract
    contract = {
        "run_id": run_id,
        "raw_user_prompt": "Generate a CLI tool that processes a CSV file.",
        "intent": "Create a CSV processing CLI tool",
        "cleaned_goal": "Create a CLI tool that reads data.csv and prints summary",
        "final_outputs": ["cli_tool.py"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": [],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "HARD",
        "done_criteria": ["cli_tool.py exists", "cli_tool.py processes CSV correctly"],
        "failure_criteria": ["cli_tool.py missing", "CSV processing fails"],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": "Create a CLI tool that reads data.csv and prints summary"
    }
    (run_dir / "goal_contract.json").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "goal_contract.json").write_text(json.dumps(contract, indent=2))
    # Run plan_router
    result = subprocess.run([sys.executable, ".agentic-pi/runtime/plan_router.py", "--run-id", run_id],
                            cwd=Path.cwd(),
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("plan_router failed:", result.stderr)
        sys.exit(1)
    # Create data.csv in artifacts folder
    artifact_dir = run_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifact_dir / "data.csv"
    csv_path.write_text("col1,col2\n1,2\n3,4\n")
    # Run cli_tool.py
    cli_path = artifact_dir / "cli_tool.py"
    if not cli_path.is_file():
        print("cli_tool.py not found")
        sys.exit(1)
    result = subprocess.run([sys.executable, str(cli_path)], capture_output=True, text=True)
    out = result.stdout.strip()
    # Check output
    assert "Rows: 2" in out, f"Expected row count 2, got: {out}"
    assert "Columns: 2" in out, f"Expected column count 2, got: {out}"
    print("CSV processing test passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
