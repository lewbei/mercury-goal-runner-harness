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


class PlanningProofHardeningTests(unittest.TestCase):
    def tearDown(self):
        for run_dir in RUN_ROOT.glob("pi_smoke_planning_proof_*"):
            shutil.rmtree(run_dir)

    def run_planning_case(self):
        run_id = "pi_smoke_planning_proof_p2"
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
            "planning_p2",
        )
        self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
        self.assertEqual(load_json(run_dir / "goal_contract.json")["complexity_level"], "HARD")

        proof_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-plan-proof",
            run_id,
        )
        self.assertEqual(proof_result.returncode, 0, proof_result.stdout)
        return run_dir

    def test_raw_goal_reaches_selected_branch_then_certified_done(self):
        run_dir = self.run_planning_case()

        branch_manifest = load_json(run_dir / "branch_manifest.json")
        self.assertEqual(
            [row["branch_id"] for row in branch_manifest["branches"]],
            ["B.MINIMAL", "B.ROBUST", "B.SKEPTIC"],
        )

        branch_decision = load_json(run_dir / "branch_decision.json")
        self.assertEqual(branch_decision["decision_status"], "SELECTED")
        self.assertEqual(branch_decision["selected_branch"], "B.MINIMAL")

        selector_audit = load_json(run_dir / "selector_audit.json")
        self.assertTrue(selector_audit["status_artifacts_absent"])

        merged_plan = load_json(run_dir / "merged_plan.json")
        self.assertEqual(merged_plan["planner"], "planning-proof-runner-v1.2")
        self.assertEqual(merged_plan["selected_branch"], "B.MINIMAL")
        self.assertEqual(merged_plan["branch_candidate_path"], "branches/B.MINIMAL/branch_candidate.json")
        self.assertEqual(len(merged_plan["steps"]), 2)
        produced_artifact = merged_plan["steps"][0]["produces"][0]["artifact_id"]
        self.assertEqual(merged_plan["steps"][1]["requires"], [produced_artifact])
        self.assertEqual(merged_plan["steps"][1]["produces"][0]["artifact_id"], "A.FINAL_OUTPUT")

        plan_graph = load_json(run_dir / "plan_graph.json")
        self.assertIn(
            {
                "source": produced_artifact,
                "target": "T.SELECTED_BRANCH_FINAL_OUTPUT",
                "type": "requires",
            },
            plan_graph["edges"],
        )

        certification = load_json(run_dir / "certification.json")
        policy = load_json(run_dir / "policy_decision.json")
        proof = load_json(run_dir / "planning_proof.json")
        self.assertEqual(certification["status"], "CERTIFIED_DONE")
        self.assertEqual(policy["status"], "CERTIFIED_DONE")
        self.assertEqual(proof["final_status"], "CERTIFIED_DONE")
        self.assertEqual(proof["final_status_source"], "certification.json")
        self.assertEqual(proof["selected_branch"], "B.MINIMAL")
        self.assertEqual(proof["invariant"], "Planner selects; certifier decides.")

    def test_goal_plan_proof_is_exposed_but_not_final_authority(self):
        help_result = run_python(".agentic-pi/runtime/pi_cli.py", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stdout)
        self.assertIn("goal-plan-proof", help_result.stdout)
        self.assertIn("Final status comes only from", help_result.stdout)

    def test_v12_doc_locks_planning_boundary(self):
        doc = (ROOT / "docs" / "V1_2_PLANNING_PROOF_HARDENING.md").read_text(encoding="utf-8")

        self.assertIn("PLANNING PROOF HARDENING IMPLEMENTED", doc)
        self.assertIn("raw goal", doc)
        self.assertIn("-> branch candidates", doc)
        self.assertIn("-> selected branch", doc)
        self.assertIn("-> merged_plan.json", doc)
        self.assertIn("Planner proposes.", doc)
        self.assertIn("Certifier writes final status.", doc)
        self.assertIn("does not prove", doc)
        self.assertIn("Mercury can generate high-quality plans", doc)


if __name__ == "__main__":
    unittest.main()
