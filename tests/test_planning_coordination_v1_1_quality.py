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
QUALITY_GATE = ".agentic-pi/runtime/planning_coordination_v1_1_quality.py"
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


def resolve_reported_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


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


class PlanningCoordinationV11QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="planning_coordination_v1_1_test_"))
        self.goal = self.tmpdir / "goal.json"
        self.stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.work_dir = self.tmpdir / "planning_coordination_v1_1"
        self.output = self.tmpdir / "planning_coordination_v1_1_quality_report.json"
        write_json(self.goal, load_json(COORDINATION_GOAL))
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(self.stage3_report))
        if stage3.returncode != 0:
            raise AssertionError(stage3.stdout)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        for run_dir in (ROOT / ".agentic-runs").glob("planning_coordination_v1_1_test_exec_*"):
            shutil.rmtree(run_dir, ignore_errors=True)

    def run_quality_gate(self, *extra):
        return run_python(
            QUALITY_GATE,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(self.work_dir),
            "--output", str(self.output),
            *extra,
        )

    def test_quality_gate_approves_repaired_candidate_with_blocker_budget(self):
        result = self.run_quality_gate()
        report = load_json(self.output)
        plan_quality = load_json(self.work_dir / "plan_quality_report.json")
        blocker_budget = load_json(self.work_dir / "blocker_budget_report.json")
        skeptic_review = load_json(self.work_dir / "planning_skeptic_review_report.json")
        attack_resolution = load_json(self.work_dir / "planning_attack_resolution_report.json")
        coordination_report = load_json(self.work_dir / "coordination_v1_report.json")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_1_QUALITY_APPROVED")
        self.assertEqual(report["selected_candidate_id"], "planning_efficiency_v3_repair_loop")
        self.assertGreaterEqual(report["quality_score"], 0.85)
        self.assertEqual(plan_quality["status"], "PLAN_QUALITY_APPROVED")
        self.assertEqual(blocker_budget["status"], "WITHIN_BUDGET")
        self.assertEqual(blocker_budget["current_blocking_unknowns"], 0)
        self.assertLessEqual(blocker_budget["current_nonblocking_unknowns"], 3)
        self.assertEqual(skeptic_review["status"], "SKEPTIC_REVIEW_APPROVED")
        self.assertEqual(skeptic_review["review_mode"], "planning_only")
        self.assertEqual(attack_resolution["status"], "ATTACK_RESOLUTION_APPROVED")
        self.assertIn("skeptic_attack_review", plan_quality["quality_scores"])
        self.assertFalse(skeptic_review["runtime_execution"]["guarded_execution_invoked"])
        self.assertFalse(skeptic_review["runtime_execution"]["can_certify_done"])
        self.assertTrue(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["required_next_runtime"], "guarded_execution_v2")
        self.assertIn("planning_skeptic_review_report", report["quality_artifacts"])
        self.assertIn("planning_attack_resolution_report", report["quality_artifacts"])
        self.assertIn("planning_only_skeptic_review_passed", {check["check_id"] for check in report["criteria"]})
        self.assertEqual(coordination_report["selected_candidate_id"], "planning_efficiency_v3_repair_loop")
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])

    def test_clean_goal_quality_gate_prefers_direct_candidate(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][0]["content"] = "Planning Coordination v1.1 clean direct candidate content."
        write_json(self.goal, goal)

        result = self.run_quality_gate()
        report = load_json(self.output)
        plan_quality = load_json(self.work_dir / "plan_quality_report.json")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["selected_candidate_id"], "direct_v2_preflight")
        self.assertEqual(plan_quality["selected_candidate_id"], "direct_v2_preflight")
        self.assertEqual(report["unknown_budget"]["status"], "WITHIN_BUDGET")

    def test_failed_stage3_blocks_quality_gate_without_inputs(self):
        failed_stage3 = load_json(self.stage3_report)
        failed_stage3["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        failed_stage3["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.stage3_report, failed_stage3)

        result = self.run_quality_gate()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_1_NOT_READY")
        self.assertFalse(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["guarded_execution_inputs"], {})
        self.assertGreater(report["unknown_budget"]["current_blocking_unknowns"], 0)

    def test_over_budget_goal_blocks_quality_gate_without_fallback_execution(self):
        goal = load_json(self.goal)
        while len(goal["artifact_specs"]) <= 5:
            index = len(goal["artifact_specs"]) + 1
            goal["artifact_specs"].append({
                "artifact_id": f"A.QUALITY_EXTRA_{index}",
                "name": f"quality_extra_{index}",
                "requested_path": f"artifacts/planning_coordination_v1_1_extra_{index}.txt",
                "content": "Extra artifact that makes every candidate over budget.",
            })
        write_json(self.goal, goal)

        result = self.run_quality_gate()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_1_NOT_READY")
        self.assertTrue(report["execution_gate"]["blocked_before_execution"])
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])

    def test_tampered_selected_plan_blocks_reused_coordination_report(self):
        coordination_work = self.tmpdir / "coordination_v1"
        coordination_report = self.tmpdir / "coordination_v1_report.json"
        initial = run_python(
            COORDINATOR,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(coordination_work),
            "--output", str(coordination_report),
        )
        self.assertEqual(initial.returncode, 0, initial.stdout)
        report = load_json(coordination_report)
        plan_path = Path(report["execution_gate"]["guarded_execution_inputs"]["plan"])
        if not plan_path.is_absolute():
            plan_path = ROOT / plan_path
        plan = load_json(plan_path)
        plan["actions"][0]["content"] = "tampered after preflight hash binding"
        write_json(plan_path, plan)

        result = self.run_quality_gate("--reuse-coordination-report", str(coordination_report))
        quality_report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(quality_report["status"], "PLANNING_COORDINATION_V1_1_NOT_READY")
        self.assertFalse(quality_report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertIn("dependency_coverage", json.dumps(quality_report["unknown_budget"]))

    def test_unresolved_selected_candidate_skeptic_risk_blocks_handoff(self):
        coordination_work = self.tmpdir / "coordination_v1_skeptic"
        coordination_report_path = self.tmpdir / "coordination_v1_skeptic_report.json"
        initial = run_python(
            COORDINATOR,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(coordination_work),
            "--output", str(coordination_report_path),
        )
        self.assertEqual(initial.returncode, 0, initial.stdout)
        coordination_report = load_json(coordination_report_path)
        selected = coordination_report["selected_candidate_id"]
        risk_path = resolve_reported_path(coordination_report["planning_artifacts"]["planning_risk_attack_report"])
        risk_report = load_json(risk_path)
        for risk in risk_report["risks"]:
            if risk.get("risk_id") == f"R.CANDIDATE_{selected}":
                risk["status"] = "FAIL"
                risk["mitigation"] = "unresolved selected-candidate skeptic finding"
        write_json(risk_path, risk_report)

        result = self.run_quality_gate("--reuse-coordination-report", str(coordination_report_path))
        report = load_json(self.output)
        skeptic_review = load_json(self.work_dir / "planning_skeptic_review_report.json")
        attack_resolution = load_json(self.work_dir / "planning_attack_resolution_report.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_1_NOT_READY")
        self.assertEqual(skeptic_review["status"], "SKEPTIC_REVIEW_BLOCKED")
        self.assertEqual(attack_resolution["status"], "ATTACK_RESOLUTION_BLOCKED")
        self.assertFalse(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["guarded_execution_inputs"], {})
        self.assertIn("skeptic_attack_review", json.dumps(report["unknown_budget"]))
        self.assertIn(f"R.CANDIDATE_{selected}", json.dumps(skeptic_review["unresolved_high_or_authority_risks"]))

    def test_unresolved_authority_skeptic_risk_blocks_handoff(self):
        coordination_work = self.tmpdir / "coordination_v1_authority"
        coordination_report_path = self.tmpdir / "coordination_v1_authority_report.json"
        initial = run_python(
            COORDINATOR,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(coordination_work),
            "--output", str(coordination_report_path),
        )
        self.assertEqual(initial.returncode, 0, initial.stdout)
        coordination_report = load_json(coordination_report_path)
        risk_path = resolve_reported_path(coordination_report["planning_artifacts"]["planning_risk_attack_report"])
        risk_report = load_json(risk_path)
        for risk in risk_report["risks"]:
            if risk.get("risk_id") == "R.AUTHORITY_LEAK":
                risk["status"] = "FAIL"
                risk["mitigation"] = "authority boundary is unresolved"
        write_json(risk_path, risk_report)

        result = self.run_quality_gate("--reuse-coordination-report", str(coordination_report_path))
        report = load_json(self.output)
        attack_resolution = load_json(self.work_dir / "planning_attack_resolution_report.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_COORDINATION_V1_1_NOT_READY")
        self.assertFalse(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["guarded_execution_inputs"], {})
        self.assertEqual(attack_resolution["status"], "ATTACK_RESOLUTION_BLOCKED")
        self.assertIn("R.AUTHORITY_LEAK", json.dumps(attack_resolution["unresolved_high_or_authority_risks"]))

    def test_module_validation_requires_skeptic_artifact_metadata(self):
        module = load_runtime_module("planning_coordination_v1_1_quality")
        result = self.run_quality_gate()
        report = load_json(self.output)
        report["quality_artifacts"].pop("planning_skeptic_review_report")
        report["quality_artifact_hashes"].pop("planning_skeptic_review_report")

        self.assertEqual(result.returncode, 0, result.stdout)
        errors = module.validate_quality_gate_report(report)
        self.assertIn("quality_artifacts.planning_skeptic_review_report is required", errors)
        self.assertIn("quality_artifact_hashes.planning_skeptic_review_report is required", errors)

    def test_skeptic_artifact_validation_rejects_execution_claim(self):
        module = load_runtime_module("planning_coordination_v1_1_quality")
        result = self.run_quality_gate()
        report = load_json(self.output)
        skeptic_review = load_json(self.work_dir / "planning_skeptic_review_report.json")
        attack_resolution = load_json(self.work_dir / "planning_attack_resolution_report.json")
        skeptic_review["runtime_execution"]["guarded_execution_invoked"] = True

        self.assertEqual(result.returncode, 0, result.stdout)
        errors = module.validate_skeptic_review_reports(skeptic_review, attack_resolution, report["selected_candidate_id"])
        self.assertIn("skeptic review: guarded_execution_invoked must be false", errors)

    def test_selected_candidate_can_be_consumed_by_guarded_execution_v2(self):
        result = self.run_quality_gate()
        report = load_json(self.output)
        inputs = report["execution_gate"]["guarded_execution_inputs"]
        run_id = f"planning_coordination_v1_1_test_exec_{self.tmpdir.name[-8:]}"
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
        result = self.run_quality_gate()
        report_text = self.output.read_text(encoding="utf-8")
        protected_names = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(any(path.name in protected_names for path in self.work_dir.rglob("*")))
        for status_value in ["CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"]:
            self.assertNotIn(status_value, report_text)

    def test_module_validation_rejects_guarded_execution_claim(self):
        module = load_runtime_module("planning_coordination_v1_1_quality")
        result = self.run_quality_gate()
        report = load_json(self.output)
        report["runtime_execution"]["guarded_execution_invoked"] = True

        self.assertEqual(result.returncode, 0, result.stdout)
        errors = module.validate_quality_gate_report(report)
        self.assertIn("runtime_execution.guarded_execution_invoked must be false", errors)


if __name__ == "__main__":
    unittest.main()
