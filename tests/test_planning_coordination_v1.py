import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
STAGE3_PREFLIGHT = ".agentic-pi/runtime/stage3_runtime_preflight.py"
COORDINATOR = ".agentic-pi/runtime/planning_coordination_v1.py"
GUARDED_EXECUTION_V2 = ".agentic-pi/runtime/guarded_execution_v2.py"
COORDINATION_GOAL = RUNTIME / "planning_coordination_v1_goal.json"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime_module(module_name: str):
    sys.path.insert(0, str(RUNTIME.resolve()))
    try:
        spec = importlib.util.spec_from_file_location(module_name, RUNTIME / f"{module_name}.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class PlanningCoordinationV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="planning_coordination_v1_test_"))
        self.goal = self.tmpdir / "goal.json"
        self.stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.work_dir = self.tmpdir / "planning_coordination_v1"
        self.output = self.tmpdir / "planning_coordination_v1_report.json"
        write_json(self.goal, load_json(COORDINATION_GOAL))
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(self.stage3_report))
        if stage3.returncode != 0:
            raise AssertionError(stage3.stdout)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for run_dir in (ROOT / ".agentic-runs").glob("planning_coordination_v1_test_exec_*"):
            shutil.rmtree(run_dir, ignore_errors=True)

    def run_coordinator(self, *extra):
        return run_python(
            COORDINATOR,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(self.work_dir),
            "--output", str(self.output),
            *extra,
        )

    def test_repair_candidate_selected_after_direct_preflight_fails(self):
        result = self.run_coordinator()
        report = load_json(self.output)
        candidates = load_json(self.work_dir / "candidate_plans.json")
        completeness = load_json(self.work_dir / "planning_completeness_report.json")
        direct = next(item for item in candidates["candidates"] if item["candidate_id"] == "direct_v2_preflight")
        repair = next(item for item in candidates["candidates"] if item["candidate_id"] == "planning_efficiency_v3_repair_loop")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_APPROVED")
        self.assertEqual(report["selected_candidate_id"], "planning_efficiency_v3_repair_loop")
        self.assertEqual(direct["status"], "PREFLIGHT_FAIL")
        self.assertIn("TOKEN_PATTERN", direct["repair_hint_codes"])
        self.assertEqual(repair["status"], "PREFLIGHT_PASS")
        self.assertEqual(completeness["status"], "APPROVED_FOR_EXECUTION")
        self.assertTrue(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["required_next_runtime"], "guarded_execution_v2")
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])

    def test_clean_goal_selects_direct_candidate_without_repair(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][0]["content"] = "Planning Coordination v1 clean direct candidate content."
        write_json(self.goal, goal)

        result = self.run_coordinator()
        report = load_json(self.output)
        candidates = load_json(self.work_dir / "candidate_plans.json")
        direct = next(item for item in candidates["candidates"] if item["candidate_id"] == "direct_v2_preflight")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["selected_candidate_id"], "direct_v2_preflight")
        self.assertEqual(direct["status"], "PREFLIGHT_PASS")
        self.assertEqual(direct["metrics"]["repair_attempts_used"], 0)

    def test_failed_stage3_preflight_blocks_selection(self):
        failed_stage3 = load_json(self.stage3_report)
        failed_stage3["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        failed_stage3["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.stage3_report, failed_stage3)

        result = self.run_coordinator()
        report = load_json(self.output)
        completeness = load_json(self.work_dir / "planning_completeness_report.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_NOT_READY")
        self.assertEqual(report["selected_candidate_id"], "")
        self.assertFalse(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(completeness["status"], "BLOCKED_NO_VALID_CANDIDATE")

    def test_over_budget_goal_stops_not_ready_without_fallback_execution(self):
        goal = load_json(self.goal)
        while len(goal["artifact_specs"]) <= 5:
            index = len(goal["artifact_specs"]) + 1
            goal["artifact_specs"].append({
                "artifact_id": f"A.COORDINATION_EXTRA_{index}",
                "name": f"coordination_extra_{index}",
                "requested_path": f"artifacts/planning_coordination_v1_extra_{index}.txt",
                "content": "Extra artifact that makes candidate generation over budget.",
            })
        write_json(self.goal, goal)

        result = self.run_coordinator()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_NOT_READY")
        self.assertEqual(report["selected_candidate_id"], "")
        self.assertTrue(report["execution_gate"]["blocked_before_execution"])
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])

    def test_selected_candidate_can_be_consumed_by_guarded_execution_v2(self):
        result = self.run_coordinator()
        report = load_json(self.output)
        inputs = report["execution_gate"]["guarded_execution_inputs"]
        run_id = f"planning_coordination_v1_test_exec_{self.tmpdir.name[-8:]}"
        exec_report = self.tmpdir / "guarded_execution_v2_report.json"
        ledger = self.tmpdir / "guarded_execution_v2_ledger.json"

        execution = run_python(
            GUARDED_EXECUTION_V2,
            "--preflight-report", inputs["preflight_report"],
            "--plan", inputs["plan"],
            "--expected-artifacts", inputs["expected_artifacts"],
            "--planning-preflight-report", inputs["planning_preflight_report"],
            "--run-id", run_id,
            "--output", str(exec_report),
            "--ledger-output", str(ledger),
        )
        execution_report = load_json(exec_report)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(execution_report["status"], "GUARDED_EXECUTION_V2_PASS")
        self.assertTrue(execution_report["runtime_execution"]["planning_preflight_checked"])
        self.assertFalse(execution_report["runtime_execution"]["can_certify_done"])

    def test_report_contains_no_protected_status_artifacts_or_final_status_values(self):
        result = self.run_coordinator()
        report_text = self.output.read_text(encoding="utf-8")
        protected_names = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(any(path.name in protected_names for path in self.work_dir.rglob("*")))
        for status_value in ["CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"]:
            self.assertNotIn(status_value, report_text)

    def test_protected_output_name_is_refused(self):
        result = run_python(
            COORDINATOR,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(self.work_dir),
            "--output", str(self.tmpdir / "final_status.json"),
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_module_validation_rejects_guarded_execution_claim(self):
        module = load_runtime_module("planning_coordination_v1")
        result = self.run_coordinator()
        report = load_json(self.output)
        report["runtime_execution"]["guarded_execution_invoked"] = True

        self.assertEqual(result.returncode, 0, result.stdout)
        errors = module.validate_coordination_report(report)
        self.assertIn("runtime_execution.guarded_execution_invoked must be false", errors)


if __name__ == "__main__":
    unittest.main()
