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


def goal_contract(run_id: str, raw_goal: str, final_output: str) -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": raw_goal,
        "intent": raw_goal,
        "cleaned_goal": raw_goal,
        "final_outputs": [final_output],
        "explicit_constraints": ["Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic milestone planner proof."],
        "forbidden_actions": ["Do not certify DONE in milestone artifacts."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "SIMPLE",
        "done_criteria": [f"{final_output} exists."],
        "failure_criteria": [f"{final_output} missing."],
        "ask_user_conditions": [],
        "max_steps": 8,
        "execution_prompt": raw_goal,
    }


class MilestonePlanningTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def make_run(self, suffix: str, raw_goal: str, final_output: str) -> Path:
        run_id = f"test_milestone_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        write_json(run_dir / "goal_contract.json", goal_contract(run_id, raw_goal, final_output))
        (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
        return run_dir

    def prepare_selected_strategy(self, run_dir: Path):
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
            ".agentic-pi/runtime/strategy_selector.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

    def prepare_milestones(self, run_dir: Path):
        self.prepare_selected_strategy(run_dir)
        for tool in [
            ".agentic-pi/runtime/milestone_builder.py",
            ".agentic-pi/runtime/milestone_tracker.py",
            ".agentic-pi/runtime/local_step_planner.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_milestone_builder_creates_domain_milestones(self):
        cases = [
            (
                "writing",
                "Write a README.md document for the harness",
                "README.md",
                ["outline", "draft", "verify constraints", "finalize"],
            ),
            (
                "coding",
                "Create a Python CLI script for CSV summary",
                "tool.py",
                ["reproduce/inspect", "patch", "verify", "certify"],
            ),
            (
                "research",
                "Create a paper source novelty claim audit",
                "artifacts/research.md",
                ["define claim", "collect closest sources", "build comparison matrix", "attack novelty", "final verdict"],
            ),
        ]
        for suffix, raw_goal, final_output, expected_titles in cases:
            with self.subTest(suffix=suffix):
                run_dir = self.make_run(suffix, raw_goal, final_output)
                self.prepare_selected_strategy(run_dir)
                result = run_python(".agentic-pi/runtime/milestone_builder.py", str(run_dir))
                self.assertEqual(result.returncode, 0, result.stdout)

                milestone_plan = load_json(run_dir / "milestone_plan.json")
                self.assertEqual([row["title"] for row in milestone_plan["milestones"]], expected_titles)
                self.assertEqual(milestone_plan["final_status_authority"], "certifier_only")
                schema = run_python(
                    ".agentic-pi/validators/validate_schema.py",
                    ".agentic-pi/schemas/milestone_plan.schema.json",
                    str(run_dir / "milestone_plan.json"),
                )
                self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_milestone_tracker_records_deterministic_planned_statuses(self):
        run_dir = self.make_run("tracker", "Write a README.md document for the harness", "README.md")
        self.prepare_selected_strategy(run_dir)
        for tool in [
            ".agentic-pi/runtime/milestone_builder.py",
            ".agentic-pi/runtime/milestone_tracker.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

        status = load_json(run_dir / "milestone_status.json")
        self.assertEqual(status["allowed_statuses"], ["planned", "active", "complete", "blocked"])
        self.assertEqual({row["status"] for row in status["milestone_statuses"]}, {"planned"})
        self.assertEqual(status["final_status_authority"], "certifier_only")
        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/milestone_status.schema.json",
            str(run_dir / "milestone_status.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_local_step_plan_preserves_milestone_order_and_dependencies(self):
        run_dir = self.make_run("local_steps", "Write a README.md document for the harness", "README.md")
        self.prepare_milestones(run_dir)

        milestone_ids = [row["milestone_id"] for row in load_json(run_dir / "milestone_plan.json")["milestones"]]
        local_steps = load_json(run_dir / "local_step_plan.json")["local_steps"]
        self.assertEqual([row["milestone_id"] for row in local_steps], milestone_ids)
        self.assertEqual(local_steps[0]["requires"], [])
        for index in range(1, len(local_steps)):
            previous_artifact = local_steps[index - 1]["produces"][0]["artifact_id"]
            self.assertEqual(local_steps[index]["requires"], [previous_artifact])
        self.assertEqual(local_steps[-1]["path"], "README.md")
        self.assertEqual(local_steps[-1]["produces"][0]["artifact_id"], "A.FINAL_OUTPUT")
        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/local_step_plan.schema.json",
            str(run_dir / "local_step_plan.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_step_compiler_consumes_local_step_plan_when_present(self):
        run_dir = self.make_run("compile", "Write a README.md document for the harness", "README.md")
        self.prepare_milestones(run_dir)
        result = run_python(".agentic-pi/runtime/step_compiler.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        merged_plan = load_json(run_dir / "merged_plan.json")
        local_steps = load_json(run_dir / "local_step_plan.json")["local_steps"]
        self.assertEqual(merged_plan["planner"], "step-compiler-v1.4")
        self.assertEqual(merged_plan["milestone_source"], "local_step_plan.json")
        self.assertEqual(len(merged_plan["steps"]), len(local_steps))
        self.assertEqual([step["milestone_id"] for step in merged_plan["steps"]], [step["milestone_id"] for step in local_steps])
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_goal_milestone_proof_reaches_certified_done_for_p2_fixture(self):
        run_id = f"pi_smoke_milestone_{self._testMethodName}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

        compile_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-compile",
            run_id,
            "--goal",
            "Create README.md explaining the harness",
            "--mode",
            "p2",
        )
        self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
        proof_result = run_python(".agentic-pi/runtime/pi_cli.py", "goal-milestone-proof", run_id)
        self.assertEqual(proof_result.returncode, 0, proof_result.stdout)

        self.assertEqual(load_json(run_dir / "milestone_plan.json")["generated_by"], "milestone-builder-v1.4")
        self.assertEqual(load_json(run_dir / "local_step_plan.json")["generated_by"], "local-step-planner-v1.4")
        self.assertEqual(load_json(run_dir / "merged_plan.json")["planner"], "step-compiler-v1.4")
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "CERTIFIED_DONE")
        self.assertEqual(load_json(run_dir / "policy_decision.json")["status"], "CERTIFIED_DONE")
        proof = load_json(run_dir / "milestone_proof.json")
        self.assertEqual(proof["final_status"], "CERTIFIED_DONE")
        self.assertEqual(proof["final_status_source"], "certification.json")
        self.assertEqual(proof["milestone_count"], proof["local_step_count"])
        self.assertEqual(proof["local_step_count"], proof["merged_plan_step_count"])

    def test_unknown_milestone_proof_does_not_fake_done(self):
        run_dir = self.make_run("unknown", "blue sky purpose with no operational keyword", "artifacts/output.txt")
        result = run_python(".agentic-pi/runtime/milestone_proof_runner.py", run_dir.name)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(load_json(run_dir / "milestone_proof.json")["final_status"], "NEED_USER_STRATEGY")
        self.assertFalse((run_dir / "milestone_plan.json").exists())
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_v14_doc_locks_milestone_boundary(self):
        doc = (ROOT / "docs" / "V1_4_MILESTONE_PLANNING.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("MILESTONE PLANNING IMPLEMENTED", doc)
        self.assertIn("milestone_plan.json", doc)
        self.assertIn("local_step_plan.json", doc)
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("does not prove", doc.lower())
        self.assertIn("v1.4 Milestone Planning", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)
        self.assertIn("v1.6 Trajectory-Level Evaluation", roadmap)
        self.assertIn("DEFERRED", roadmap)


if __name__ == "__main__":
    unittest.main()
