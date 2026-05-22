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


def base_contract(run_id: str, artifact_tests=None):
    contract = {
        "run_id": run_id,
        "raw_user_prompt": "test verifier provenance runtime",
        "intent": "test verifier provenance runtime",
        "cleaned_goal": "create out.txt",
        "final_outputs": ["out.txt"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": ["Do not touch protected files."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "SIMPLE",
        "done_criteria": ["out.txt exists."],
        "failure_criteria": ["out.txt missing."],
        "ask_user_conditions": [],
        "max_steps": 3,
        "execution_prompt": "create out.txt",
    }
    if artifact_tests is not None:
        contract["artifact_tests"] = artifact_tests
    return contract


def verifier_contract(run_id: str, required_level="P2"):
    return {
        "run_id": run_id,
        "target_goal": "Create out.txt",
        "target_artifacts": ["out.txt"],
        "required_verifier_level": required_level,
        "allow_self_generated_only": False,
        "required_behaviors": ["out.txt exists"],
        "forbidden_verifier_patterns": ["same-worker self-test"],
        "minimum_strength_level": "certifying",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"],
    }


class VerifierProvenanceRuntimeTests(unittest.TestCase):
    def setUp(self):
        safe_name = self._testMethodName.replace("test_", "")
        self.run_id = f"test_provenance_{safe_name}_{os.getpid()}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "step_logs").mkdir()
        (self.run_dir / "trace.jsonl").write_text(
            json.dumps({"event": "test_start"}) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def write_successful_output_and_log(self, touched_path="out.txt"):
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        if touched_path != "out.txt":
            touched = self.run_dir / touched_path
            touched.parent.mkdir(parents=True, exist_ok=True)
            touched.write_text("worker-forged verifier\n", encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "1.json",
            {
                "run_id": self.run_id,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": [touched_path],
                "commands_run": [f"write {touched_path}"],
                "evidence": [f"{touched_path} exists"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )

    def certify(self, certify_validator=True):
        verifier_dir = self.run_dir / "verifier_artifacts"
        if certify_validator and verifier_dir.is_dir() and any(verifier_dir.glob("*.json")):
            validator_result = run_python(".agentic-pi/validators/validator_factory.py", str(self.run_dir))
            self.assertEqual(validator_result.returncode, 0, validator_result.stdout)
        return run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

    def add_covered_criteria(self, artifact_id, criteria=None):
        artifact_path = self.run_dir / "verifier_artifacts" / f"{artifact_id}.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["covered_criteria"] = criteria or ["out.txt exists."]
        write_json(artifact_path, artifact)

    def load_certification(self):
        return json.loads((self.run_dir / "certification.json").read_text(encoding="utf-8"))

    def add_verifier_contract(self):
        write_json(self.run_dir / "verifier_contract.json", verifier_contract(self.run_id))

    def add_verifier_artifact(
        self,
        artifact_id,
        source,
        phase="post_solution",
        depends_on_solution=None,
        solution_exists_at_creation=None,
    ):
        args = [
            ".agentic-pi/runtime/verifier_provenance.py",
            "--run-id",
            self.run_id,
            "--artifact-id",
            artifact_id,
            "--target",
            "out.txt",
            "--source",
            source,
            "--phase",
            phase,
            "--kind",
            "command_test",
            "--assertion-count",
            "2",
        ]
        if depends_on_solution is not None:
            args.extend(["--depends-on-solution", str(depends_on_solution).lower()])
        if solution_exists_at_creation is not None:
            args.extend([
                "--solution-exists-at-creation",
                str(solution_exists_at_creation).lower(),
            ])
        result = run_python(*args)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.add_covered_criteria(artifact_id)

    def test_logger_records_solution_existence_before_and_after_target(self):
        before = run_python(
            ".agentic-pi/runtime/verifier_provenance.py",
            "--run-id",
            self.run_id,
            "--artifact-id",
            "V.BEFORE",
            "--target",
            "out.txt",
            "--source",
            "same_run_worker",
            "--phase",
            "post_solution",
            "--kind",
            "command_test",
        )
        self.assertEqual(before.returncode, 0, before.stdout)
        (self.run_dir / "out.txt").write_text("real output\n", encoding="utf-8")
        after = run_python(
            ".agentic-pi/runtime/verifier_provenance.py",
            "--run-id",
            self.run_id,
            "--artifact-id",
            "V.AFTER",
            "--target",
            "out.txt",
            "--source",
            "same_run_worker",
            "--phase",
            "post_solution",
            "--kind",
            "command_test",
        )
        self.assertEqual(after.returncode, 0, after.stdout)

        before_artifact = json.loads(
            (self.run_dir / "verifier_artifacts" / "V.BEFORE.json").read_text(encoding="utf-8")
        )
        after_artifact = json.loads(
            (self.run_dir / "verifier_artifacts" / "V.AFTER.json").read_text(encoding="utf-8")
        )
        self.assertFalse(before_artifact["solution_exists_at_creation"])
        self.assertTrue(after_artifact["solution_exists_at_creation"])

    def test_legacy_run_without_verifier_contract_still_done_passes(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.write_successful_output_and_log()

        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "DONE_PASS")

    def test_provenance_mode_without_verifier_artifacts_is_not_done(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.add_verifier_contract()
        self.write_successful_output_and_log()

        result = self.certify()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "NOT_DONE")
        self.assertIn("verifier_artifacts missing", result.stdout)

    def test_p0_verifier_evidence_is_only_provisional(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.add_verifier_contract()
        self.write_successful_output_and_log()
        self.add_verifier_artifact("V.P0", "same_run_worker")

        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "PROVISIONAL_DONE")

    def test_p1_visible_verifier_evidence_is_only_provisional_when_p2_required(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.add_verifier_contract()
        self.write_successful_output_and_log()
        self.add_verifier_artifact("V.P1", "existing_repo_test")

        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "PROVISIONAL_DONE")

    def test_p2_verifier_evidence_certifies_done(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.add_verifier_contract()
        self.write_successful_output_and_log()
        self.add_verifier_artifact(
            "V.P2",
            "independent_verifier_agent",
            phase="pre_solution",
            depends_on_solution=False,
            solution_exists_at_creation=False,
        )

        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "CERTIFIED_DONE")

    def test_goal_contract_artifact_tests_are_logged_as_p1_and_remain_provisional(self):
        (self.run_dir / "probe.py").write_text("print('ok')\n", encoding="utf-8")
        write_json(
            self.run_dir / "goal_contract.json",
            base_contract(
                self.run_id,
                artifact_tests=[
                    {
                        "test_id": "VISIBLE_TEST",
                        "type": "command",
                        "cmd": "python probe.py",
                        "expect_exit_code": 0,
                        "expect_stdout_contains": ["ok"],
                        "expect_stdout_lines_min": 1,
                    }
                ],
            ),
        )
        self.add_verifier_contract()
        self.write_successful_output_and_log()

        first_result = self.certify(certify_validator=False)

        self.assertNotEqual(first_result.returncode, 0, first_result.stdout)
        logged = self.run_dir / "verifier_artifacts" / "V.ARTIFACT_TEST.VISIBLE_TEST.json"
        self.assertTrue(logged.is_file())
        artifact = json.loads(logged.read_text(encoding="utf-8"))
        self.assertEqual(artifact["provenance_level"], "P1")
        self.assertEqual(artifact["source"], "existing_repo_test")

        self.add_covered_criteria("V.ARTIFACT_TEST.VISIBLE_TEST")
        result = self.certify()

        self.assertEqual(result.returncode, 0, result.stdout)
        certification = self.load_certification()
        self.assertEqual(certification["status"], "PROVISIONAL_DONE")

    def test_worker_touched_verifier_artifact_is_rejected(self):
        write_json(self.run_dir / "goal_contract.json", base_contract(self.run_id))
        self.add_verifier_contract()
        self.write_successful_output_and_log(touched_path="verifier_artifacts/V.BAD.json")
        self.add_verifier_artifact("V.P2", "independent_verifier_agent")

        result = self.certify(certify_validator=False)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.load_certification()["status"], "NOT_DONE")
        self.assertIn("protected provenance path", result.stdout)


if __name__ == "__main__":
    unittest.main()
