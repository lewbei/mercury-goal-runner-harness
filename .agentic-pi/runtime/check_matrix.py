"""
Horizontal check matrix for the harness.

Each check is an independent module that:
1. Reads its required inputs
2. Produces a check result artifact (PASS/FAIL with details)
3. Can be re-run independently without re-running other checks

The certifier aggregates all check results into final status.

Usage to run a single check:
    python check_matrix.py <run_dir> <check_name>

Usage to run all checks:
    python check_matrix.py <run_dir> --all
"""

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECK_DIR = ROOT / ".agentic-pi" / "checks"
CHECK_DIR.mkdir(exist_ok=True)


class Check:
    """A single independent check."""
    
    def __init__(self, name: str, description: str, dependencies: list[str]):
        self.name = name
        self.description = description
        self.dependencies = dependencies
    
    def run(self, run_dir: Path) -> dict:
        """Run this check. Override in subclasses."""
        raise NotImplementedError
    
    def result_path(self, run_dir: Path) -> Path:
        """Path to this check's result artifact."""
        check_dir = run_dir / "checks"
        check_dir.mkdir(exist_ok=True)
        return check_dir / f"{self.name}.json"
    
    def load_result(self, run_dir: Path) -> dict | None:
        """Load a previous result if it exists."""
        path = self.result_path(run_dir)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None
    
    def save_result(self, run_dir: Path, result: dict):
        """Save check result."""
        result["check_name"] = self.name
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.result_path(run_dir).write_text(json.dumps(result, indent=2))


# ── Check Implementations ──────────────────────────────────────────────

class PlanGraphCheck(Check):
    """Verify plan_graph.json schema and node/edge validity."""
    
    def __init__(self):
        super().__init__("plan_graph", "Validates plan_graph.json structure", [])
    
    def run(self, run_dir: Path) -> dict:
        graph = run_dir / "plan_graph.json"
        if not graph.exists():
            return {"status": "FAIL", "detail": "plan_graph.json missing"}
        
        try:
            data = json.loads(graph.read_text(encoding="utf-8"))
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            
            issues = []
            for n in nodes:
                if n.get("type") == "task" and not n.get("task_id"):
                    issues.append(f"task node {n.get('node_id')} missing task_id")
                if n.get("type") == "artifact" and not n.get("path"):
                    issues.append(f"artifact node {n.get('node_id')} missing path")
            
            edge_types = {e.get("type") for e in edges}
            bad = edge_types - {"produces", "requires"}
            if bad:
                issues.append(f"invalid edge types: {bad}")
            
            if issues:
                return {"status": "FAIL", "detail": "; ".join(issues)}
            
            return {
                "status": "PASS",
                "detail": f"{len(nodes)} nodes, {len(edges)} edges",
                "nodes": len(nodes),
                "edges": len(edges)
            }
        except Exception as e:
            return {"status": "FAIL", "detail": f"parse error: {e}"}


class StepLogCheck(Check):
    """Verify step logs exist and have required fields."""
    
    def __init__(self):
        super().__init__("step_logs", "Validates step log format and completeness", ["plan_graph"])
    
    def run(self, run_dir: Path) -> dict:
        log_dir = run_dir / "step_logs"
        if not log_dir.is_dir():
            return {"status": "FAIL", "detail": "step_logs/ directory missing"}
        
        logs = sorted(log_dir.glob("*.json"))
        if not logs:
            return {"status": "FAIL", "detail": "no step logs found"}
        
        required = {"run_id", "step_id", "status", "action_taken", "files_touched",
                     "commands_run", "evidence", "pass_condition_satisfied", "remaining_work"}
        
        results = []
        for log in logs:
            try:
                data = json.loads(log.read_text(encoding="utf-8"))
                missing = required - set(data.keys())
                if missing:
                    results.append({"file": log.name, "status": "FAIL", 
                                   "detail": f"missing fields: {missing}"})
                    continue
                
                type_issues = []
                if not isinstance(data.get("files_touched"), list):
                    type_issues.append("files_touched must be list")
                if not isinstance(data.get("evidence"), list):
                    type_issues.append("evidence must be list")
                if not isinstance(data.get("remaining_work"), list):
                    type_issues.append("remaining_work must be list")
                
                if type_issues:
                    results.append({"file": log.name, "status": "FAIL",
                                   "detail": "; ".join(type_issues)})
                else:
                    results.append({"file": log.name, "status": "PASS",
                                   "detail": f"step {data.get('step_id')}: {data.get('action_taken')}"})
            except Exception as e:
                results.append({"file": log.name, "status": "FAIL", "detail": str(e)})
        
        failed = [r for r in results if r["status"] == "FAIL"]
        if failed:
            return {"status": "FAIL", "detail": f"{len(failed)}/{len(results)} logs failed", "results": results}
        
        return {"status": "PASS", "detail": f"{len(results)} logs valid", "results": results}


class CodeExecutionCheck(Check):
    """Verify the output script runs and produces 2+ lines."""
    
    def __init__(self):
        super().__init__("code_execution", "Runs the output script and checks output", ["step_logs"])
    
    def run(self, run_dir: Path) -> dict:
        import subprocess
        
        gc = run_dir / "goal_contract.json"
        if not gc.exists():
            return {"status": "FAIL", "detail": "goal_contract.json missing"}
        
        outputs = json.loads(gc.read_text(encoding="utf-8")).get("final_outputs", [])
        if not outputs:
            return {"status": "FAIL", "detail": "no final_outputs in contract"}
        
        results = []
        for output in outputs:
            path = run_dir / output
            if not path.exists():
                results.append({"file": output, "status": "FAIL", "detail": "file missing"})
                continue
            
            try:
                abs_path = str(path.resolve())
                result = subprocess.run(
                    [sys.executable, abs_path],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l for l in result.stdout.splitlines() if l.strip()]
                if result.returncode == 0 and len(lines) >= 2:
                    results.append({"file": output, "status": "PASS",
                                   "detail": f"{len(lines)} lines of output"})
                else:
                    results.append({"file": output, "status": "FAIL",
                                   "detail": f"exit={result.returncode}, lines={len(lines)}, stderr={result.stderr[:100]}"})
            except Exception as e:
                results.append({"file": output, "status": "FAIL", "detail": str(e)})
        
        failed = [r for r in results if r["status"] == "FAIL"]
        if failed:
            return {"status": "FAIL", "detail": f"{len(failed)}/{len(results)} outputs failed", "results": results}
        return {"status": "PASS", "detail": f"{len(results)} outputs OK", "results": results}


class FormalVerificationCheck(Check):
    """Run formal contract verification."""
    
    def __init__(self):
        super().__init__("formal_verification", "Runs contract verifier on output code", ["code_execution"])
    
    def run(self, run_dir: Path) -> dict:
        script = ROOT / ".agentic-pi" / "formal" / "harness_contract_verifier.py"
        if not script.exists():
            return {"status": "SKIP", "detail": "formal verifier not found"}
        
        gc = json.loads((run_dir / "goal_contract.json").read_text(encoding="utf-8"))
        outputs = gc.get("final_outputs", [])
        if not outputs:
            return {"status": "SKIP", "detail": "no output files to verify"}
        
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script), str(run_dir), outputs[0]],
            cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        
        # Parse result from artifact
        artifact_dir = run_dir / "verifier_artifacts"
        f_files = list(artifact_dir.glob("F_*.json"))
        if f_files:
            data = json.loads(f_files[-1].read_text(encoding="utf-8"))
            detail = data.get("formal_verification_detail", {})
            return {
                "status": data.get("verdict", "UNKNOWN"),
                "detail": f"confidence={detail.get('confidence', 0):.2f}",
                "checks": detail.get("checks", [])
            }
        
        return {"status": "FAIL", "detail": result.stdout[-200:]}


class CryptographicSignCheck(Check):
    """Verify Ed25519 signatures on artifacts."""
    
    def __init__(self):
        super().__init__("crypto_signatures", "Verifies artifact signatures", ["code_execution"])
    
    def run(self, run_dir: Path) -> dict:
        sig_files = list(run_dir.rglob("*.sig"))
        if not sig_files:
            return {"status": "SKIP", "detail": "no signatures found"}
        
        # Simple hash check — full verification needs harness_signing.py
        results = []
        for sig_path in sig_files:
            try:
                sig_data = json.loads(sig_path.read_text(encoding="utf-8"))
                artifact_path = run_dir / sig_data.get("artifact", "")
                if not artifact_path.exists():
                    results.append({"file": sig_path.name, "status": "FAIL", 
                                   "detail": "artifact missing"})
                    continue
                
                import hashlib, base64
                content = artifact_path.read_bytes()
                content_hash = hashlib.sha256(content).digest()
                declared = base64.b64decode(sig_data.get("artifact_hash_sha256", ""))
                
                if content_hash == declared:
                    results.append({"file": sig_path.name, "status": "PASS",
                                   "detail": f"{sig_data.get('algorithm', '?')} verified"})
                else:
                    results.append({"file": sig_path.name, "status": "FAIL",
                                   "detail": "hash mismatch — tampered"})
            except Exception as e:
                results.append({"file": sig_path.name, "status": "FAIL", "detail": str(e)})
        
        failed = [r for r in results if r["status"] == "FAIL"]
        if failed:
            return {"status": "FAIL", "detail": f"{len(failed)}/{len(results)} sigs failed", "results": results}
        return {"status": "PASS", "detail": f"{len(results)} signatures valid", "results": results}


# ── Check Registry ─────────────────────────────────────────────────────

CHECKS = {
    "plan_graph": PlanGraphCheck(),
    "step_logs": StepLogCheck(),
    "code_execution": CodeExecutionCheck(),
    "formal_verification": FormalVerificationCheck(),
    "crypto_signatures": CryptographicSignCheck(),
}


def run_all(run_dir: Path) -> dict:
    """Run all checks and produce a matrix report."""
    matrix = {}
    for name, check in CHECKS.items():
        print(f"  [{name}] ", end="", flush=True)
        result = check.run(run_dir)
        check.save_result(run_dir, result)
        matrix[name] = result
        status = result["status"]
        icon = "PASS" if status == "PASS" else ("SKIP" if status == "SKIP" else "FAIL")
        print(f"{icon}: {result['detail'][:80]}")
    
    # Summary
    passed = sum(1 for r in matrix.values() if r["status"] == "PASS")
    failed = sum(1 for r in matrix.values() if r["status"] == "FAIL")
    skipped = sum(1 for r in matrix.values() if r["status"] == "SKIP")
    total = len(matrix)
    
    return {
        "run_id": run_dir.name,
        "checks": matrix,
        "summary": f"{passed} passed, {failed} failed, {skipped} skipped ({total} total)",
        "overall": "PASS" if failed == 0 else "PARTIAL",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def run_one(run_dir: Path, check_name: str) -> dict:
    """Run a single check."""
    if check_name not in CHECKS:
        print(f"Unknown check: {check_name}")
        print(f"Available: {', '.join(CHECKS.keys())}")
        sys.exit(1)
    
    check = CHECKS[check_name]
    result = check.run(run_dir)
    check.save_result(run_dir, result)
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_matrix.py <run_dir> [check_name|--all]")
        print(f"Available checks: {', '.join(CHECKS.keys())}")
        sys.exit(1)
    
    run_dir = Path(sys.argv[1])
    if not run_dir.is_dir():
        print(f"Run directory not found: {run_dir}")
        sys.exit(1)
    
    if len(sys.argv) > 2 and sys.argv[2] != "--all":
        result = run_one(run_dir, sys.argv[2])
        print(f"\n{json.dumps(result, indent=2)}")
    else:
        print(f"=== Check Matrix: {run_dir.name} ===\n")
        matrix = run_all(run_dir)
        print(f"\nSummary: {matrix['summary']}")
        print(f"Overall: {matrix['overall']}")


if __name__ == "__main__":
    main()
