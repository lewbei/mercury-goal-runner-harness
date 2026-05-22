import json
import os
import shutil
import subprocess
import sys
import unittest
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


def base_contract(run_id: str):
    return {
        "run_id": run_id,
        "raw_user_prompt": "test artifact-linked PlanGraph",
        "intent": "test artifact handoff",
        "cleaned_goal": "create report from exact artifact handoff",
        "final_outputs": ["report.txt"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": ["Do not touch protected files."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "MEDIUM",
        "done_criteria": ["report.txt exists.", "report.txt contains the word 'A.SOURCE'."],
        "failure_criteria": ["report.txt missing.", "artifact handoff invalid."],
        "ask_user_conditions": [],
        "max_steps": 3,
        "execution_prompt": "test artifact handoff",
    }


def two_task_plan(
    t1_artifact_id="A.SOURCE",
    t1_path="artifacts/source.txt",
    t2_requires=None,
    report_content="report consumed A.SOURCE\n",
):
    if t2_requires is None:
        t2_requires = ["A.SOURCE"]
    return {
        "planner": "test-planner",
        "steps": [
            {
                "task_id": "T1",
                "action": "create_file",
                "path": t1_path,
                "content": "source data\n",
                "requires": [],
                "produces": [
                    {
                        "artifact_id": t1_artifact_id,
                        "path": t1_path,
                    }
                ],
            },
            {
                "task_id": "T2",
                "action": "create_file",
                "path": "report.txt",
                "content": report_content,
                "requires": t2_requires,
                "produces": [
                    {
                        "artifact_id": "A.REPORT",
                        "path": "report.txt",
                    }
                ],
            },
        ],
    }


class PlanGraphTests(unittest.TestCase):
    def setUp(self):
        safe_name = self._testMethodName.replace("test_", "")
        self.run_id = f"test_plangraph_{safe_name}_{os.getpid()}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def build_execute_and_link(self):
        for args in [
            (".agentic-pi/runtime/plan_graph_builder.py", self.run_id),
            (".agentic-pi/runtime/guarded_worker.py", "--run-id", self.run_id),
            (".agentic-pi/runtime/artifact_linker.py", self.run_id),
            (".agentic-pi/runtime/task_graph_builder.py", self.run_id),
        ]:
            result = run_python(*args)
            self.assertEqual(result.returncode, 0, result.stdout)

    def certify(self):
        return run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

    def validate_graph(self):
        return run_python(".agentic-pi/validators/validate_plan_graph.py", str(self.run_dir))

    def test_valid_two_task_graph_passes(self):
        write_json(self.run_dir / "merged_plan.json", two_task_plan())

        self.build_execute_and_link()
        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        certification = json.loads((self.run_dir / "certification.json").read_text(encoding="utf-8"))
        self.assertIn("PlanGraph validation passed", certification["passed_checks"])

    def test_missing_required_artifact_file_fails(self):
        write_json(self.run_dir / "merged_plan.json", two_task_plan())
        self.build_execute_and_link()
        (self.run_dir / "artifacts" / "source.txt").unlink()

        result = self.certify()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("produced artifact missing at exact path", result.stdout)

    def test_unproduced_required_artifact_id_fails(self):
        write_json(self.run_dir / "merged_plan.json", two_task_plan(t2_requires=["A.MISSING"]))

        self.build_execute_and_link()
        result = self.certify()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("required artifact has no producer", result.stdout)

    def test_existing_path_with_wrong_artifact_id_fails(self):
        write_json(
            self.run_dir / "merged_plan.json",
            two_task_plan(t1_artifact_id="A.WRONG", t2_requires=["A.SOURCE"]),
        )

        self.build_execute_and_link()
        result = self.certify()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.run_dir / "artifacts" / "source.txt").is_file())
        self.assertIn("required artifact has no producer", result.stdout)

    def test_artifact_path_escape_fails_builder(self):
        write_json(
            self.run_dir / "merged_plan.json",
            two_task_plan(t1_path="../outside.txt"),
        )

        result = run_python(".agentic-pi/runtime/plan_graph_builder.py", self.run_id)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("artifact path escapes run folder", result.stdout)

    def test_unknown_graph_field_fails_schema_validation(self):
        write_json(self.run_dir / "merged_plan.json", two_task_plan())
        self.build_execute_and_link()
        graph_path = self.run_dir / "plan_graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["nodes"][0]["unexpected"] = True
        write_json(graph_path, graph)

        result = self.validate_graph()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unexpected field 'unexpected'", result.stdout)


if __name__ == "__main__":
    unittest.main()
