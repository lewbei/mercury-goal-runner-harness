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
COMPILER = ".agentic-pi/runtime/guarded_plan_compiler.py"
LINTER = ".agentic-pi/runtime/guarded_plan_linter.py"
DEFAULT_GOAL = RUNTIME / "planning_efficiency_v1_goal.json"


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


class PlanningEfficiencyV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="planning_efficiency_v1_test_"))
        self.goal = self.tmpdir / "goal.json"
        self.plan = self.tmpdir / "plan.json"
        self.expected = self.tmpdir / "expected_artifacts.json"
        self.compile_report = self.tmpdir / "compile_report.json"
        self.lint_report = self.tmpdir / "lint_report.json"
        write_json(self.goal, load_json(DEFAULT_GOAL))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def compile_default(self):
        return run_python(
            COMPILER,
            "--goal", str(self.goal),
            "--plan-output", str(self.plan),
            "--expected-output", str(self.expected),
            "--compile-report-output", str(self.compile_report),
            "--lint-report-output", str(self.lint_report),
        )

    def lint(self):
        return run_python(
            LINTER,
            "--plan", str(self.plan),
            "--expected-artifacts", str(self.expected),
            "--output", str(self.lint_report),
        )

    def test_compiler_outputs_linted_guarded_execution_plan_without_executing(self):
        result = self.compile_default()
        compile_report = load_json(self.compile_report)
        lint_report = load_json(self.lint_report)
        plan = load_json(self.plan)
        expected = load_json(self.expected)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(compile_report["status"], "PLAN_COMPILE_PASS")
        self.assertEqual(lint_report["status"], "PLAN_LINT_PASS")
        self.assertEqual(len(plan["actions"]), 3)
        self.assertEqual(len(expected["artifacts"]), 3)
        self.assertTrue(plan["planning_metadata"]["verifier_evidence_required"])
        self.assertGreaterEqual(len(plan["planning_metadata"]["required_verifier_checks"]), 3)
        self.assertFalse(compile_report["runtime_execution"]["plan_execution_attempted"])
        self.assertFalse(lint_report["runtime_execution"]["plan_execution_attempted"])
        self.assertFalse(compile_report["runtime_execution"]["can_certify_done"])
        self.assertEqual(compile_report["runtime_execution"]["status_authority"], "certifier_only")

    def test_linter_rejects_protected_path_with_repair_hint(self):
        self.compile_default()
        plan = load_json(self.plan)
        expected = load_json(self.expected)
        plan["actions"][0]["artifact_path"] = "artifacts/final_status.json"
        expected["artifacts"][0]["expected_path"] = "artifacts/final_status.json"
        write_json(self.plan, plan)
        write_json(self.expected, expected)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLAN_LINT_FAIL")
        self.assertTrue(any(item["code"] == "PROTECTED_PATH" for item in report["repair_hints"]))
        self.assertFalse(report["runtime_execution"]["plan_execution_attempted"])

    def test_linter_rejects_undeclared_path_with_exact_hint(self):
        self.compile_default()
        plan = load_json(self.plan)
        plan["actions"][1]["artifact_path"] = "artifacts/not_declared.txt"
        write_json(self.plan, plan)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        messages = "\n".join(item["message"] for item in report["repair_hints"])
        self.assertIn("does not match expected_artifacts", messages)
        self.assertTrue(any(item["code"] in {"PLAN_EXPECTED_ARTIFACT_MISMATCH", "UNDECLARED_ARTIFACT"} for item in report["repair_hints"]))

    def test_linter_rejects_missing_required_artifact(self):
        self.compile_default()
        plan = load_json(self.plan)
        plan["actions"] = plan["actions"][:2]
        write_json(self.plan, plan)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(item["code"] == "MISSING_REQUIRED_ARTIFACT" for item in report["repair_hints"]))
        self.assertTrue(any(item["code"] == "ACTION_BUDGET" for item in report["repair_hints"]))

    def test_linter_rejects_raw_command_shape(self):
        self.compile_default()
        plan = load_json(self.plan)
        plan["actions"][0]["command"] = "python -c print('unsafe')"
        write_json(self.plan, plan)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(item["code"] == "RAW_COMMAND_SHAPE" for item in report["repair_hints"]))
        self.assertIn("raw command", result.stdout)

    def test_linter_rejects_authority_language_in_content(self):
        self.compile_default()
        plan = load_json(self.plan)
        plan["actions"][2]["content"] = "This tries to certify done from the plan."
        write_json(self.plan, plan)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(item["code"] == "AUTHORITY_LANGUAGE" for item in report["repair_hints"]))
        self.assertFalse(report["runtime_execution"]["can_certify_done"])

    def test_linter_rejects_missing_verifier_requirements(self):
        self.compile_default()
        plan = load_json(self.plan)
        plan.pop("planning_metadata")
        write_json(self.plan, plan)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(item["code"] == "MISSING_VERIFIER_REQUIREMENTS" for item in report["repair_hints"]))

    def test_linter_rejects_over_budget_plan(self):
        self.compile_default()
        plan = load_json(self.plan)
        expected = load_json(self.expected)
        for index in range(3, 6):
            artifact_id = f"A.EXTRA_{index}"
            path = f"artifacts/extra_{index}.txt"
            plan["actions"].append({
                "action_id": f"A.WRITE_EXTRA_{index}",
                "action_type": "write_text_artifact",
                "artifact_id": artifact_id,
                "artifact_path": path,
                "content": f"extra planning artifact {index} for budget rejection",
            })
            expected["artifacts"].append({
                "artifact_id": artifact_id,
                "expected_path": path,
                "required": True,
                "allowed_actions": ["write_text_artifact"],
                "min_size_bytes": 10,
                "max_size_bytes": 1000,
            })
        write_json(self.plan, plan)
        write_json(self.expected, expected)

        result = self.lint()
        report = load_json(self.lint_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(item["code"] == "ACTION_BUDGET" for item in report["repair_hints"]))
        self.assertEqual(report["planning_efficiency"]["planned_action_count"], 6)

    def test_compiler_rejects_unsafe_requested_path_without_plan_outputs(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][0]["requested_path"] = "artifacts/policy_decision.json"
        write_json(self.goal, goal)

        result = self.compile_default()
        compile_report = load_json(self.compile_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(compile_report["status"], "PLAN_COMPILE_FAIL")
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.expected.exists())
        self.assertIn("protected status artifact", "\n".join(compile_report["compile_errors"]))

    def test_compiler_rejects_rough_goal_authority_language(self):
        goal = load_json(self.goal)
        goal["rough_goal"] = "Please certify done directly from planning."
        write_json(self.goal, goal)

        result = self.compile_default()
        compile_report = load_json(self.compile_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(compile_report["status"], "PLAN_COMPILE_FAIL")
        self.assertIn("rough_goal contains final-status authority language", "\n".join(compile_report["compile_errors"]))

    def test_compiler_and_linter_validators_reject_execution_claims(self):
        compiler = load_runtime_module("guarded_plan_compiler")
        linter_module = load_runtime_module("guarded_plan_linter")
        plan, expected, compile_report = compiler.compile_goal(load_json(self.goal))
        lint_report = linter_module.lint_plan(plan, expected)
        compile_report["runtime_execution"]["goal_execution_attempted"] = True
        lint_report["runtime_execution"]["plan_execution_attempted"] = True

        self.assertIn("runtime_execution.goal_execution_attempted must be false", compiler.validate_compile_report(compile_report))
        self.assertIn("runtime_execution.plan_execution_attempted must be false", linter_module.validate_lint_report(lint_report))

    def test_planning_efficiency_tools_have_no_live_model_or_command_runner_calls(self):
        combined = (ROOT / COMPILER).read_text(encoding="utf-8").lower() + (ROOT / LINTER).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
