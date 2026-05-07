import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


class DriftReplanningTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def new_run_id(self, suffix: str) -> str:
        run_id = f"test_drift_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        return run_id

    def compile_p2(self, run_id: str):
        result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-compile",
            run_id,
            "--goal",
            "Create README.md explaining the harness",
            "--mode",
            "p2",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def prepare_milestone_run(self, suffix: str) -> Path:
        run_id = self.new_run_id(suffix)
        self.compile_p2(run_id)
        result = run_python(".agentic-pi/runtime/pi_cli.py", "goal-milestone-proof", run_id)
        self.assertEqual(result.returncode, 0, result.stdout)
        return RUN_ROOT / run_id

    def run_drift_tools(self, run_dir: Path, expect_fatal: bool = False):
        for tool in [
            ".agentic-pi/runtime/checkpoint_writer.py",
            ".agentic-pi/runtime/plan_monitor.py",
            ".agentic-pi/runtime/drift_detector.py",
        ]:
            result = run_python(tool, str(run_dir))
            if tool.endswith("drift_detector.py") and expect_fatal:
                self.assertNotEqual(result.returncode, 0, result.stdout)
            elif tool.endswith("plan_monitor.py") and expect_fatal:
                self.assertNotEqual(result.returncode, 0, result.stdout)
            else:
                self.assertEqual(result.returncode, 0, result.stdout)
        replan = run_python(".agentic-pi/runtime/replan_controller.py", str(run_dir))
        if expect_fatal:
            self.assertNotEqual(replan.returncode, 0, replan.stdout)
        else:
            self.assertEqual(replan.returncode, 0, replan.stdout)
        validation = run_python(".agentic-pi/validators/validate_delta_plan.py", str(run_dir))
        self.assertEqual(validation.returncode, 0, validation.stdout)

    def mutate_first_step_touched_files(self, run_dir: Path, files_touched: list[str]):
        step_path = run_dir / "step_logs" / "1.json"
        step = load_json(step_path)
        step["files_touched"] = files_touched
        step["commands_run"] = [f"write {files_touched[0]}"]
        step["evidence"] = [f"Created file {files_touched[0]}"]
        write_json(step_path, step)

    def test_matching_execution_has_drift_level_none_and_certifies(self):
        run_id = self.new_run_id("none")
        self.compile_p2(run_id)
        result = run_python(".agentic-pi/runtime/pi_cli.py", "goal-drift-proof", run_id)
        self.assertEqual(result.returncode, 0, result.stdout)
        run_dir = RUN_ROOT / run_id

        self.assertEqual(load_json(run_dir / "drift_report.json")["drift_level"], "none")
        self.assertFalse(load_json(run_dir / "drift_report.json")["blocking"])
        self.assertEqual(load_json(run_dir / "delta_plan.json")["decision_status"], "NO_DELTA_NEEDED")
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "CERTIFIED_DONE")
        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/checkpoint.schema.json",
            str(run_dir / "checkpoints" / "1.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)
        for schema_name, file_name in [
            ("drift_report.schema.json", "drift_report.json"),
            ("delta_plan.schema.json", "delta_plan.json"),
        ]:
            schema_result = run_python(
                ".agentic-pi/validators/validate_schema.py",
                f".agentic-pi/schemas/{schema_name}",
                str(run_dir / file_name),
            )
            self.assertEqual(schema_result.returncode, 0, schema_result.stdout)

    def test_wrong_artifact_path_produces_repairable_drift_and_delta_plan(self):
        run_dir = self.prepare_milestone_run("repairable")
        wrong_path = run_dir / "artifacts" / "wrong.md"
        wrong_path.parent.mkdir(parents=True, exist_ok=True)
        wrong_path.write_text("wrong artifact\n", encoding="utf-8")
        self.mutate_first_step_touched_files(run_dir, ["artifacts/wrong.md"])

        self.run_drift_tools(run_dir)

        drift = load_json(run_dir / "drift_report.json")
        delta = load_json(run_dir / "delta_plan.json")
        self.assertEqual(drift["drift_level"], "repairable")
        self.assertTrue(drift["blocking"])
        self.assertEqual(delta["decision_status"], "DELTA_PLAN_CREATED")
        self.assertTrue(delta["delta_steps"])
        self.assertTrue(load_json(run_dir / "delta_plan_validation.json")["valid"])

    def test_worker_touching_final_status_is_fatal_drift(self):
        run_dir = self.prepare_milestone_run("fatal_status")
        self.mutate_first_step_touched_files(run_dir, ["final_status.md"])

        self.run_drift_tools(run_dir, expect_fatal=True)

        drift = load_json(run_dir / "drift_report.json")
        delta = load_json(run_dir / "delta_plan.json")
        self.assertEqual(drift["drift_level"], "fatal")
        self.assertTrue(any("protected status artifact" in item for item in drift["violations"]))
        self.assertEqual(delta["decision_status"], "ABORT_REQUIRES_USER")

    def test_worker_touching_verifier_artifacts_is_fatal_drift(self):
        run_dir = self.prepare_milestone_run("fatal_verifier")
        self.mutate_first_step_touched_files(run_dir, ["verifier_artifacts/V.RAW_GOAL_P2.json"])

        self.run_drift_tools(run_dir, expect_fatal=True)

        drift = load_json(run_dir / "drift_report.json")
        self.assertEqual(drift["drift_level"], "fatal")
        self.assertTrue(any("protected provenance path" in item for item in drift["violations"]))

    def test_delta_plan_validator_rejects_status_artifact_write(self):
        run_dir = self.prepare_milestone_run("bad_delta")
        write_json(
            run_dir / "delta_plan.json",
            {
                "run_id": run_dir.name,
                "generated_by": "test",
                "decision_status": "DELTA_PLAN_CREATED",
                "drift_level": "repairable",
                "reason": "bad delta",
                "final_status_authority": "certifier_only",
                "delta_steps": [
                    {
                        "delta_step_id": "DS001",
                        "task_id": "TD.BAD",
                        "action": "create_file",
                        "path": "final_status.md",
                        "content": "CERTIFIED_DONE",
                        "produces": [{"artifact_id": "A.BAD", "path": "final_status.md"}],
                    }
                ],
            },
        )

        result = run_python(".agentic-pi/validators/validate_delta_plan.py", str(run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        report = load_json(run_dir / "delta_plan_validation.json")
        self.assertFalse(report["valid"])
        self.assertTrue(any("protected status artifact" in item for item in report["violations"]))

    def test_certifier_blocks_blocking_or_invalid_drift_report(self):
        run_dir = self.prepare_milestone_run("certifier_blocks")
        write_json(
            run_dir / "drift_report.json",
            {
                "run_id": run_dir.name,
                "generated_by": "test",
                "generated_at": "2026-05-07T00:00:00Z",
                "valid": True,
                "drift_level": "fatal",
                "blocking": True,
                "recommended_action": "abort_requires_user",
                "violations": ["worker touched protected status artifact: final_status.md"],
            },
        )
        result = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "NOT_DONE")
        self.assertTrue(
            any("drift_report.json blocks certification" in item for item in load_json(run_dir / "certification.json")["failed_checks"])
        )

        write_json(
            run_dir / "drift_report.json",
            {
                "run_id": run_dir.name,
                "generated_by": "test",
                "drift_level": "none",
            },
        )
        invalid = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))
        self.assertNotEqual(invalid.returncode, 0, invalid.stdout)
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "NOT_DONE")
        self.assertTrue(
            any("drift_report.json schema validation failed" in item for item in load_json(run_dir / "certification.json")["failed_checks"])
        )

    def test_v15_doc_locks_drift_boundary(self):
        doc = (ROOT / "docs" / "V1_5_DRIFT_AWARE_REPLANNING.md").read_text(encoding="utf-8")

        self.assertIn("DRIFT-AWARE REPLANNING IMPLEMENTED", doc)
        self.assertIn("drift_report.json", doc)
        self.assertIn("delta_plan.json", doc)
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("does not prove", doc.lower())


if __name__ == "__main__":
    unittest.main()
