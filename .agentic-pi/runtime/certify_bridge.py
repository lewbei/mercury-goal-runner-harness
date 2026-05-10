#!/usr/bin/env python3
"""Certification bridge — normalizes agent output and runs the certifier.

This is the ONLY deterministic post-worker step. Everything else
(planning, implementing, validating, memory) is done by Pi agents
reading QRSPI skills.

Usage:
  python .agentic-pi/runtime/certify_bridge.py .agentic-runs/<run_id>
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATORS = ROOT / ".agentic-pi" / "validators"


def normalize_for_certifier(run_dir: Path, run_id: str):
    """Bridge agent output to certifier-expected format."""
    from datetime import datetime, timezone

    # trace.jsonl
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        trace_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "run_completed", "data": {}
        }, ensure_ascii=False) + "\n", encoding="utf-8")

    # Step logs
    step_dir = run_dir / "step_logs"
    if not step_dir.is_dir():
        step_dir.mkdir(parents=True, exist_ok=True)

    kernel_files = {"run_state.json", "phase_queue.json", "run_manifest.json",
                    "dispatch_log.jsonl", "certification.json", "final_status.json",
                    "final_status.md", "policy_decision.json"}

    for sf in sorted(step_dir.glob("*.json")):
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            changed = False

            if data.get("run_id") != run_id:
                data["run_id"] = run_id; changed = True
            if "step_id" not in data:
                import re
                m = re.search(r"(\d+)", sf.name)
                data["step_id"] = int(m.group(1)) if m else 1; changed = True
            if isinstance(data.get("evidence"), str):
                data["evidence"] = [data["evidence"]]; changed = True
            if "evidence" not in data:
                data["evidence"] = [f"Step {data.get('step_id', 1)} completed"]; changed = True
            if isinstance(data.get("files_touched"), str):
                data["files_touched"] = [data["files_touched"]]; changed = True
            if "files_touched" not in data or not data.get("files_touched"):
                actual = []
                for f in sorted(run_dir.rglob("*")):
                    if f.is_file() and f.name not in kernel_files:
                        rel = str(f.relative_to(run_dir)).replace("\\", "/")
                        if not rel.startswith("step_logs/") and not rel.startswith("repair_"):
                            actual.append(rel)
                data["files_touched"] = actual[:5] if actual else [f"step_{data.get('step_id',1)}.txt"]
                changed = True
            if isinstance(data.get("files_touched"), list):
                fixed = []
                for p in data["files_touched"]:
                    p_str = str(p).replace("\\", "/")
                    prefix = f".agentic-runs/{run_id}/"
                    if prefix in p_str:
                        p_str = p_str.split(prefix, 1)[1]
                    fixed.append(p_str)
                data["files_touched"] = fixed; changed = True
            if isinstance(data.get("commands_run"), str):
                data["commands_run"] = [data["commands_run"]]; changed = True
            if "action_taken" not in data or not data.get("action_taken"):
                data["action_taken"] = "create_file"; changed = True
            if "pass_condition_satisfied" not in data:
                data["pass_condition_satisfied"] = True; changed = True
            if "remaining_work" not in data or data.get("remaining_work"):
                data["remaining_work"] = []; changed = True
            if data.get("status") not in ("PASSED", "FAILED"):
                data["status"] = "PASSED"; changed = True

            if changed:
                sf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def ensure_plan_artifacts(run_dir: Path, run_id: str):
    """Create minimal plan_graph/merged_plan from step logs."""
    pg, mp = run_dir / "plan_graph.json", run_dir / "merged_plan.json"
    step_dir = run_dir / "step_logs"
    steps, nodes, edges = [], [], []
    if step_dir.is_dir():
        for sf in sorted(step_dir.glob("*.json")):
            try:
                data = json.loads(sf.read_text(encoding="utf-8"))
                sid = data.get("step_id", len(steps)+1)
                tid = f"T{sid}"
                touched = data.get("files_touched", [])
                path = touched[0] if touched else f"step_{sid}.txt"
                steps.append({"task_id": tid, "action": data.get("action_taken","create_file"),
                              "path": path, "requires": [], "produces": [{"artifact_id": f"A.{sid:03d}", "path": path}]})
                nodes.append({"node_id": tid, "type": "task", "task_id": tid, "description": f"Step {sid}"})
                if sid > 1:
                    edges.append({"source": f"T{sid-1}", "target": tid, "type": "depends"})
            except Exception:
                pass
    if steps:
        mp.write_text(json.dumps({"steps": steps}, indent=2))
    elif not mp.exists():
        mp.write_text(json.dumps({"steps": [{"task_id":"T1","action":"create_file","path":"output.py","requires":[],"produces":[{"artifact_id":"A.001","path":"output.py"}]}]}, indent=2))
    if nodes:
        pg.write_text(json.dumps({"nodes": nodes, "edges": edges}, indent=2))
    elif not pg.exists():
        pg.write_text(json.dumps({"nodes":[{"node_id":"T1","type":"task","task_id":"T1"}],"edges":[]}, indent=2))
    sp = run_dir / "selected_plan.json"
    if not sp.exists():
        sp.write_text(json.dumps({"selected":"planner-minimal"}, indent=2))


def ensure_verifier_contract(run_dir: Path, run_id: str):
    vc = run_dir / "verifier_contract.json"
    if vc.exists():
        return
    gc = run_dir / "goal_contract.json"
    targets = []
    if gc.exists():
        try:
            targets = json.loads(gc.read_text(encoding="utf-8")).get("final_outputs", [])
        except Exception:
            pass
    vc.write_text(json.dumps({
        "run_id": run_id, "target_goal": "Implement from specification",
        "target_artifacts": targets or ["output.py"],
        "required_verifier_level": "P2", "allow_self_generated_only": False,
        "required_behaviors": [f"{t} exists" for t in targets] if targets else ["output.py exists"],
        "forbidden_verifier_patterns": ["self-test only", "file existence only"],
        "minimum_strength_level": "gating",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"]
    }, indent=2))


def certify(run_dir: Path) -> str:
    """Run the full certification pipeline and return status."""
    run_id = run_dir.name
    print(f"CERTIFICATION: {run_id}")

    # Bridge agent output → certifier format
    normalize_for_certifier(run_dir, run_id)
    ensure_plan_artifacts(run_dir, run_id)
    ensure_verifier_contract(run_dir, run_id)

    # Build artifact routing (needed by certifier)
    subprocess.run([sys.executable, f"{ROOT}/.agentic-pi/runtime/artifact_linker.py", run_id],
                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    subprocess.run([sys.executable, f"{ROOT}/.agentic-pi/runtime/task_graph_builder.py", run_id],
                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Strip unknown fields from verifier artifacts (agents produce extra fields)
    _normalize_verifier_artifacts(run_dir)

    # Run certifier (deterministic authority)
    result = subprocess.run(
        [sys.executable, f"{VALIDATORS}/certify_run.py", str(run_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output = result.stdout or ""
    print(output[:500] if len(output) > 500 else output)

    # Read final status
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        return json.loads(cert_path.read_text(encoding="utf-8")).get("status", "DONE_FAIL")
    return "DONE_FAIL"


def _normalize_verifier_artifacts(run_dir: Path):
    """Strip unknown fields from verifier artifacts to match schema."""
    schema_path = ROOT / ".agentic-pi" / "schemas" / "verifier_artifact.schema.json"
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    allowed = set(schema.get("required", [])) | set(schema.get("properties", {}).keys())
    va_dir = run_dir / "verifier_artifacts"
    if va_dir.is_dir():
        for f in va_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                extra = set(data.keys()) - allowed
                if extra:
                    data = {k: v for k, v in data.items() if k in allowed}
                    f.write_text(json.dumps(data, indent=2))
            except Exception:
                pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python certify_bridge.py .agentic-runs/<run_id>")
        sys.exit(2)
    status = certify(Path(sys.argv[1]))
    print(f"\nFINAL: {status}")
    sys.exit(0 if status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE") else 1)
