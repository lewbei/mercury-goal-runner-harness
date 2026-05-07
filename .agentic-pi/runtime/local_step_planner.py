#!/usr/bin/env python3
"""Convert milestone_plan.json into executable local_step_plan.json."""
import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def artifact_token(milestone_id: str) -> str:
    return milestone_id.upper().replace(" ", "_")


def intermediate_path(milestone_id: str) -> str:
    return f"artifacts/milestones/{milestone_id.lower().replace('.', '_')}.md"


def final_content(strategy_id: str, task_type: str, final_output: str) -> str:
    if final_output.endswith(".py"):
        return (
            "#!/usr/bin/env python3\n"
            "print('Rows: 1')\n"
            "print('Columns: 1')\n"
        )
    if task_type == "research":
        return "# Research Verdict\n\nClaims remain bounded until verifier provenance certifies the evidence.\n"
    if task_type == "benchmark":
        return "# Benchmark Diagnostic\n\nExpected-vs-actual status and false PASS checks are required.\n"
    if task_type == "debugging":
        return "# Debugging Result\n\nReproduced, patched, and prepared for verifier checks.\n"
    if task_type == "coding":
        return "# Coding Result\n\nThe harness still requires behavior evidence before certification.\n"
    return "# Harness Milestone Output\n\nThis artifact explains the harness and preserves verifier provenance.\n"


def intermediate_content(milestone: dict, selected_strategy: str) -> str:
    return (
        f"# {milestone['title']}\n\n"
        f"Milestone ID: {milestone['milestone_id']}\n\n"
        f"Selected strategy: {selected_strategy}\n\n"
        f"Purpose: {milestone['purpose']}\n\n"
        "This milestone is planning evidence only. It cannot certify DONE.\n"
    )


def plan_local_steps(run_dir: Path) -> dict:
    milestone_plan = load_json(run_dir / "milestone_plan.json")
    selected = load_json(run_dir / "selected_strategy.json")
    goal = load_json(run_dir / "goal_contract.json")
    final_outputs = goal.get("final_outputs") or ["artifacts/output.txt"]
    final_output = final_outputs[0]
    resolve_run_path(run_dir, final_output)

    local_steps = []
    previous_artifact = None
    milestones = milestone_plan.get("milestones", [])
    for index, milestone in enumerate(milestones, start=1):
        is_final = index == len(milestones)
        milestone_id = milestone["milestone_id"]
        if is_final:
            path = final_output
            artifact_id = "A.FINAL_OUTPUT"
            content = final_content(selected["strategy_id"], milestone_plan["task_type"], final_output)
        else:
            path = intermediate_path(milestone_id)
            artifact_id = f"A.{artifact_token(milestone_id)}"
            content = intermediate_content(milestone, selected["strategy_id"])
        resolve_run_path(run_dir, path)
        requires = [previous_artifact] if previous_artifact else []
        local_steps.append({
            "local_step_id": f"LS{index:03d}",
            "milestone_id": milestone_id,
            "task_id": f"T.{milestone_id}",
            "action": "create_file",
            "path": path,
            "content": content,
            "requires": requires,
            "produces": [
                {
                    "artifact_id": artifact_id,
                    "path": path,
                }
            ],
        })
        previous_artifact = artifact_id

    output = {
        "run_id": milestone_plan["run_id"],
        "generated_by": "local-step-planner-v1.4",
        "selected_strategy": selected["strategy_id"],
        "task_type": milestone_plan["task_type"],
        "source_milestone_plan": "milestone_plan.json",
        "final_status_authority": "certifier_only",
        "local_steps": local_steps,
    }
    write_json(run_dir / "local_step_plan.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert milestones into local executable steps.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = plan_local_steps(Path(args.run_dir))
    except Exception as exc:
        print(f"LOCAL_STEP_PLAN_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
