import json
import os
import shutil
import subprocess
import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def base_contract(
    run_id: str,
    final_outputs=None,
    done_criteria=None,
    complexity="SIMPLE",
    artifact_tests=None,
):
    contract = {
        "run_id": run_id,
        "raw_user_prompt": "test goal",
        "intent": "test harness behavior",
        "cleaned_goal": "test harness behavior",
        "final_outputs": final_outputs or ["out.txt"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": ["Do not touch protected files."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": complexity,
        "done_criteria": done_criteria or ["out.txt exists."],
        "failure_criteria": ["required output missing."],
        "ask_user_conditions": [],
        "max_steps": 3,
        "execution_prompt": "test harness behavior",
    }
    if artifact_tests is not None:
        contract["artifact_tests"] = artifact_tests
    return contract


def load_run_benchmark_module():
    module_path = ROOT / ".agentic-pi" / "benchmark" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessRuntimeTests(unittest.TestCase):
    def setUp(self):
        safe_name = self._testMethodName.replace("test_", "")
        self.run_id = f"test_{safe_name}_{os.getpid()}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "step_logs").mkdir()
        (self.run_dir / "artifacts").mkdir()
        (self.run_dir / "trace.jsonl").write_text(
            json.dumps({"event": "test_start"}) + "\n",
            encoding="utf-8",
        )
        self.root_artifacts_to_clean = []

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        for path in self.root_artifacts_to_clean:
            if path.exists():
                path.unlink()

    def test_guarded_worker_writes_create_file_inside_run_dir(self):
        probe_name = f"containment_probe_{os.getpid()}.txt"
        root_probe = ROOT / "artifacts" / probe_name
        if root_probe.exists():
            root_probe.unlink()
        self.root_artifacts_to_clean.append(root_probe)

        write_json(
            self.run_dir / "merged_plan.json",
            {
                "planner": "test-planner",
                "steps": [
                    {
                        "action": "create_file",
                        "path": f"artifacts/{probe_name}",
                        "content": "run scoped content",
                    }
                ],
            },
        )

        result = run_python(".agentic-pi/runtime/guarded_worker.py", "--run-id", self.run_id)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.run_dir / "artifacts" / probe_name).is_file())
        self.assertFalse(root_probe.exists(), "worker wrote outside the run folder")

    def test_plan_router_fails_closed_without_existing_planner_artifacts(self):
        write_json(
            self.run_dir / "goal_contract.json",
            base_contract(
                self.run_id,
                final_outputs=["README.md"],
                done_criteria=["README.md exists."],
                complexity="SIMPLE",
            ),
        )

        result = run_python(".agentic-pi/runtime/plan_router.py", "--run-id", self.run_id)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("STRICT_PLAN_ROUTER_REQUIRES_EXISTING_PLAN", result.stdout)
        self.assertFalse((self.run_dir / "plans" / "planner-minimal_plan.json").is_file())
        self.assertFalse((self.run_dir / "README.md").exists())
        self.assertFalse((self.run_dir / "artifacts" / "README.md").exists())

    def test_certifier_rejects_missing_touched_file(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["missing.txt"],
                "commands_run": ["write missing.txt"],
                "evidence": ["claimed missing.txt exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("touched file missing", result.stdout)

    def test_certifier_rejects_false_pass_condition(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["out.txt"],
                "commands_run": ["write out.txt"],
                "evidence": ["out.txt exists"],
                "pass_condition_satisfied": False,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("pass_condition_satisfied is not true", result.stdout)

    def test_artifact_test_rejects_placeholder_cli(self):
        write_json(
            self.run_dir / "goal_contract.json",
            base_contract(
                self.run_id,
                final_outputs=["cli_tool.py"],
                done_criteria=["When run with a sample CSV, it prints at least two lines of summary."],
                complexity="HARD",
                artifact_tests=[
                    {
                        "test_id": "CLI_SUMMARY_TEST",
                        "type": "command",
                        "cmd": "python cli_tool.py data.csv",
                        "expect_exit_code": 0,
                        "expect_stdout_contains": ["Rows", "Columns"],
                        "expect_stdout_lines_min": 2,
                    }
                ],
            ),
        )
        (self.run_dir / "data.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        (self.run_dir / "cli_tool.py").write_text(
            "print('placeholder only')\n",
            encoding="utf-8",
        )
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["cli_tool.py"],
                "commands_run": ["write cli_tool.py"],
                "evidence": ["cli_tool.py exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("artifact_test CLI_SUMMARY_TEST", result.stdout)
        self.assertIn("missing expected substring", result.stdout)

    def test_artifact_test_accepts_real_csv_cli(self):
        write_json(
            self.run_dir / "goal_contract.json",
            base_contract(
                self.run_id,
                final_outputs=["cli_tool.py"],
                done_criteria=["When run with a sample CSV, it prints at least two lines of summary."],
                complexity="HARD",
                artifact_tests=[
                    {
                        "test_id": "CLI_SUMMARY_TEST",
                        "type": "command",
                        "cmd": "python cli_tool.py data.csv",
                        "expect_exit_code": 0,
                        "expect_stdout_contains": ["Rows", "Columns"],
                        "expect_stdout_lines_min": 2,
                    }
                ],
            ),
        )
        (self.run_dir / "data.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        (self.run_dir / "cli_tool.py").write_text(
            "\n".join(
                [
                    "import csv, sys",
                    "with open(sys.argv[1], newline='') as f:",
                    "    rows = list(csv.reader(f))",
                    "print(f'Rows: {len(rows) - 1}')",
                    "print(f'Columns: {len(rows[0]) if rows else 0}')",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        write_json(
            self.run_dir / "merged_plan.json",
            {
                "planner": "test-planner",
                "steps": [
                    {
                        "action": "create_file",
                        "path": "cli_tool.py",
                        "content": "real csv cli",
                    }
                ],
            },
        )
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["cli_tool.py"],
                "commands_run": ["write cli_tool.py"],
                "evidence": ["cli_tool.py exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        certification = json.loads((self.run_dir / "certification.json").read_text(encoding="utf-8"))
        self.assertIn("artifact_test CLI_SUMMARY_TEST passed", certification["passed_checks"])

    def test_artifact_test_requires_command(self):
        write_json(
            self.run_dir / "goal_contract.json",
            base_contract(
                self.run_id,
                artifact_tests=[{"test_id": "MISSING_COMMAND", "type": "command"}],
            ),
        )
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["out.txt"],
                "commands_run": ["write out.txt"],
                "evidence": ["out.txt exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("artifact_test MISSING_COMMAND missing command", result.stdout)

    def test_certifier_requires_exact_final_output_path(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        (self.run_dir / "artifacts" / "out.txt").write_text("wrong location\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["artifacts/out.txt"],
                "commands_run": ["write artifacts/out.txt"],
                "evidence": ["artifacts/out.txt exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("final output missing: out.txt", result.stdout)

    def test_certifier_accepts_real_touched_file(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        write_json(
            self.run_dir / "merged_plan.json",
            {
                "planner": "test-planner",
                "steps": [
                    {
                        "action": "create_file",
                        "path": "out.txt",
                        "content": "real output\n",
                    }
                ],
            },
        )
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["out.txt"],
                "commands_run": ["write out.txt"],
                "evidence": ["out.txt exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("DONE_PASS", result.stdout)

    def test_risky_benchmark_expected_status_is_done_fail(self):
        run_benchmark = load_run_benchmark_module()

        expected = run_benchmark.expected_status_for(
            "impossible_goal",
            {"complexity_level": "RISKY"},
        )
        false_pass = "DONE_PASS" == "DONE_PASS" and expected != "DONE_PASS"

        self.assertEqual(expected, "DONE_FAIL")
        self.assertTrue(false_pass)


if __name__ == "__main__":
    unittest.main()
