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
PREFLIGHT = ".agentic-pi/runtime/planning_efficiency_v2_preflight.py"
REPAIR_LOOP = ".agentic-pi/runtime/planning_efficiency_v3_repair_loop.py"
REPAIR_GOAL = RUNTIME / "planning_efficiency_v3_repair_goal.json"


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


class PlanningEfficiencyV3RepairLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="planning_efficiency_v3_test_"))
        self.goal = self.tmpdir / "goal.json"
        self.stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.work_dir = self.tmpdir / "planning_efficiency_v3_repair_loop"
        self.output = self.tmpdir / "planning_efficiency_v3_repair_report.json"
        write_json(self.goal, load_json(REPAIR_GOAL))
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(self.stage3_report))
        if stage3.returncode != 0:
            raise AssertionError(stage3.stdout)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_repair_loop(self, *extra):
        return run_python(
            REPAIR_LOOP,
            "--goal", str(self.goal),
            "--stage3-preflight-report", str(self.stage3_report),
            "--work-dir", str(self.work_dir),
            "--output", str(self.output),
            *extra,
        )

    def test_default_max_repair_attempts_is_three(self):
        module = load_runtime_module("planning_efficiency_v3_repair_loop")

        self.assertEqual(module.DEFAULT_MAX_REPAIR_ATTEMPTS, 3)
        self.assertEqual(module.HARD_MAX_REPAIR_ATTEMPTS, 3)

    def test_repairable_token_goal_reaches_pass_without_executing(self):
        result = self.run_repair_loop()
        report = load_json(self.output)
        repaired_goal = load_json(self.work_dir / "planning_efficiency_v3_repaired_goal.json")
        final_preflight = load_json(self.work_dir / "planning_efficiency_v3_preflight_report.json")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V3_REPAIR_PASS")
        self.assertEqual(report["max_repair_attempts"], 3)
        self.assertEqual(report["repair_attempts_used"], 1)
        self.assertEqual(final_preflight["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_PASS")
        self.assertTrue(final_preflight["execution_gate"]["stage3_runtime_preflight_checked"])
        self.assertTrue(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertEqual(report["execution_gate"]["required_next_runtime"], "guarded_execution_v2")
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])
        self.assertNotIn("api_key", json.dumps(repaired_goal).lower())
        for path in [
            self.work_dir / "planning_efficiency_v3_plan.json",
            self.work_dir / "planning_efficiency_v3_expected_artifacts.json",
            self.work_dir / "planning_efficiency_v3_lint_report.json",
        ]:
            self.assertTrue(path.is_file(), path)

    def test_compile_failure_preflight_includes_exact_repair_hints(self):
        goal = load_json(self.goal)
        goal["artifact_specs"] = goal["artifact_specs"][:1]
        write_json(self.goal, goal)
        preflight_report = self.tmpdir / "v2_preflight_under_budget.json"

        result = run_python(
            PREFLIGHT,
            "--goal", str(self.goal),
            "--plan-output", str(self.tmpdir / "plan.json"),
            "--expected-output", str(self.tmpdir / "expected.json"),
            "--compile-report-output", str(self.tmpdir / "compile.json"),
            "--lint-report-output", str(self.tmpdir / "lint.json"),
            "--output", str(preflight_report),
            "--stage3-preflight-report", str(self.stage3_report),
        )
        report = load_json(preflight_report)
        compile_report = load_json(self.tmpdir / "compile.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL")
        self.assertTrue(any(item["code"] == "ACTION_BUDGET" for item in report["repair_hints"]))
        self.assertTrue(any(item["code"] == "ACTION_BUDGET" for item in compile_report["repair_hints"]))

    def test_under_budget_goal_is_repaired_to_minimum_actions(self):
        goal = load_json(self.goal)
        goal["artifact_specs"] = goal["artifact_specs"][:1]
        goal["artifact_specs"][0]["content"] = "Repairable under-budget artifact content."
        write_json(self.goal, goal)

        result = self.run_repair_loop()
        report = load_json(self.output)
        plan = load_json(self.work_dir / "planning_efficiency_v3_plan.json")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V3_REPAIR_PASS")
        self.assertEqual(report["repair_attempts_used"], 1)
        self.assertEqual(len(plan["actions"]), 3)

    def test_over_budget_goal_stops_not_ready_without_final_handoff(self):
        goal = load_json(self.goal)
        while len(goal["artifact_specs"]) <= 5:
            index = len(goal["artifact_specs"]) + 1
            goal["artifact_specs"].append({
                "artifact_id": f"A.EXTRA_{index}",
                "name": f"extra_{index}",
                "requested_path": f"artifacts/extra_{index}.txt",
                "content": "Extra artifact that makes over-budget repair ambiguous.",
            })
        write_json(self.goal, goal)

        result = self.run_repair_loop()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V3_NOT_READY")
        self.assertIn("ACTION_BUDGET_OVER_MAX_AMBIGUOUS", report["not_ready_reasons"])
        self.assertFalse((self.work_dir / "planning_efficiency_v3_plan.json").exists())
        self.assertFalse(report["execution_gate"]["may_pass_plan_to_guarded_execution"])

    def test_failed_stage3_preflight_hint_is_not_auto_repaired(self):
        failed_stage3 = load_json(self.stage3_report)
        failed_stage3["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        failed_stage3["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.stage3_report, failed_stage3)
        clean_goal = load_json(REPAIR_GOAL)
        clean_goal["artifact_specs"][0]["content"] = "Clean content so only Stage 3 preflight fails."
        write_json(self.goal, clean_goal)

        result = self.run_repair_loop()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V3_NOT_READY")
        self.assertIn("STAGE3_PREFLIGHT", report["not_ready_reasons"])
        self.assertEqual(report["repair_attempts_used"], 0)
        self.assertFalse((self.work_dir / "planning_efficiency_v3_plan.json").exists())

    def test_missing_repair_hints_are_not_ready(self):
        module = load_runtime_module("planning_efficiency_v3_repair_loop")
        goal = load_json(self.goal)

        repaired_goal, applied, unsupported, changed = module.apply_repair_hints(goal, [])

        self.assertEqual(repaired_goal, goal)
        self.assertEqual(applied, [])
        self.assertEqual(unsupported, ["NO_REPAIR_HINTS"])
        self.assertFalse(changed)

    def test_v3_report_contains_no_protected_status_artifacts_or_final_status_values(self):
        result = self.run_repair_loop()
        report_text = self.output.read_text(encoding="utf-8")
        protected_names = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(any(path.name in protected_names for path in self.work_dir.rglob("*")))
        for status_value in ["CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"]:
            self.assertNotIn(status_value, report_text)


if __name__ == "__main__":
    unittest.main()
