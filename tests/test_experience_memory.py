import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_memory_tests",
        ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
    )
    schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
    return validator.validate(instance, schema)


def goal_contract(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": "Create README.md explaining the harness",
        "intent": "Create README.md explaining the harness",
        "cleaned_goal": "Create README.md explaining the harness",
        "final_outputs": ["README.md"],
        "explicit_constraints": ["Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic experience memory proof."],
        "forbidden_actions": ["Do not certify DONE from memory."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "SIMPLE",
        "done_criteria": ["README.md exists."],
        "failure_criteria": ["README.md missing."],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": "Create README.md explaining the harness",
    }


def strategy_candidate(strategy_id="S.CODE_ARTIFACT_TEST") -> dict:
    return {
        "strategy_id": strategy_id,
        "task_type": "coding",
        "description": "coding strategy",
        "required_capabilities": ["python_command", "artifact_test"],
        "expected_artifacts": ["tool.py"],
        "verifier_requirements": ["P2 verifier"],
        "risk_notes": [],
        "can_reach_certifying_evidence": True,
        "uses_artifact_tests": True,
        "needs_executable_behavior": True,
        "attempts_status_write": False,
        "attempts_verifier_forgery": False,
        "status_authority": "none",
        "risk_level": "LOW",
    }


class ExperienceMemoryTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def make_completed_run(self, suffix: str, status: str, strategy_id: str = "S.CODE_ARTIFACT_TEST") -> Path:
        run_id = f"test_memory_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        write_json(run_dir / "goal_contract.json", goal_contract(run_id))
        write_json(
            run_dir / "task_type_decision.json",
            {
                "run_id": run_id,
                "task_type": "coding",
                "confidence": "high",
                "signals": ["python", "cli"],
                "generated_by": "test",
            },
        )
        write_json(
            run_dir / "strategy_decision.json",
            {
                "run_id": run_id,
                "decision_status": "SELECTED",
                "selected_strategy": strategy_id,
                "reason": "test strategy selected",
                "rejected_strategies": [],
                "selector_checks": ["test"],
                "status_artifacts_absent_before_selection": True,
            },
        )
        write_json(
            run_dir / "selected_strategy.json",
            {
                "run_id": run_id,
                "strategy_id": strategy_id,
                "task_type": "coding",
                "required_capabilities": ["python_command", "artifact_test"],
                "expected_artifacts": ["tool.py"],
                "verifier_requirements": ["P2 verifier"],
                "risk_notes": [],
                "can_reach_certifying_evidence": True,
            },
        )
        write_json(
            run_dir / "certification.json",
            {
                "run_id": run_id,
                "status": status,
                "passed_checks": [],
                "failed_checks": [] if status == "CERTIFIED_DONE" else ["test failure"],
                "artifact_hashes": {},
                "audit_chain_valid": True,
                "generated_by": "test",
                "timestamp": "2026-05-07T00:00:00+00:00",
            },
        )
        if status == "PROVISIONAL_DONE":
            write_json(
                run_dir / "verifier_smell_reports" / "V.P0_SELF.json",
                {
                    "artifact_id": "V.P0_SELF",
                    "run_id": run_id,
                    "smell_flags": ["same_worker_self_test"],
                    "disqualifying": False,
                    "authority_penalty": 2,
                },
            )
        return run_dir

    def test_certified_done_run_creates_success_learning_record(self):
        run_dir = self.make_completed_run("success", "CERTIFIED_DONE")
        with tempfile.TemporaryDirectory() as tmp:
            extract_result = run_python(".agentic-pi/runtime/experience_extractor.py", str(run_dir))
            self.assertEqual(extract_result.returncode, 0, extract_result.stdout)
            extract = load_json(run_dir / "experience_extract.json")
            self.assertEqual(extract["outcome_kind"], "success")
            self.assertFalse(extract["can_certify_done"])
            self.assertEqual(validate(extract, "experience_extract.schema.json"), [])

            write_result = run_python(
                ".agentic-pi/runtime/learning_record_writer.py",
                str(run_dir),
                "--memory-dir",
                tmp,
            )
            self.assertEqual(write_result.returncode, 0, write_result.stdout)
            record = json.loads(write_result.stdout)
            self.assertEqual(record["outcome"], "success")
            self.assertFalse(record["can_certify_done"])
            self.assertEqual(validate(record, "learning_record.schema.json"), [])
            self.assertTrue((Path(tmp) / f"{record['learning_id']}.json").is_file())

    def test_not_done_run_creates_failure_learning_record(self):
        run_dir = self.make_completed_run("failure", "NOT_DONE")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_python(".agentic-pi/runtime/experience_extractor.py", str(run_dir)).returncode, 0)
            write_result = run_python(
                ".agentic-pi/runtime/learning_record_writer.py",
                str(run_dir),
                "--memory-dir",
                tmp,
            )
            self.assertEqual(write_result.returncode, 0, write_result.stdout)
            record = json.loads(write_result.stdout)

        self.assertEqual(record["outcome"], "failure")
        self.assertIn("prior outcome status was NOT_DONE", record["do_not_use_when"])
        self.assertFalse(record["can_certify_done"])

    def test_provisional_done_records_weak_verifier_lesson(self):
        run_dir = self.make_completed_run("provisional", "PROVISIONAL_DONE")
        self.assertEqual(run_python(".agentic-pi/runtime/experience_extractor.py", str(run_dir)).returncode, 0)
        extract = load_json(run_dir / "experience_extract.json")

        self.assertEqual(extract["outcome_kind"], "provisional")
        self.assertIn("same_worker_self_test", extract["weak_verifier_patterns"])
        self.assertIn("stronger verifier evidence", extract["principle"])
        self.assertFalse(extract["can_certify_done"])

    def test_retrieved_experience_changes_strategy_score_but_cannot_bypass_gate(self):
        source_run = self.make_completed_run("source_success", "CERTIFIED_DONE")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_python(".agentic-pi/runtime/experience_extractor.py", str(source_run)).returncode, 0)
            self.assertEqual(
                run_python(
                    ".agentic-pi/runtime/learning_record_writer.py",
                    str(source_run),
                    "--memory-dir",
                    tmp,
                ).returncode,
                0,
            )

            run_dir = self.make_completed_run("target", "NOT_DONE")
            write_json(
                run_dir / "strategy_candidates.json",
                {
                    "run_id": run_dir.name,
                    "task_type": "coding",
                    "candidates": [
                        strategy_candidate("S.CODE_ARTIFACT_TEST"),
                        strategy_candidate("S.BLOCKED"),
                    ],
                },
            )
            write_json(
                run_dir / "strategy_applicability.json",
                {
                    "run_id": run_dir.name,
                    "task_type": "coding",
                    "applicable_strategies": [strategy_candidate("S.CODE_ARTIFACT_TEST")],
                    "blocked_strategies": [
                        {
                            "strategy_id": "S.BLOCKED",
                            "block_reasons": ["missing capability: imaginary_tool"],
                        }
                    ],
                },
            )
            retrieve = run_python(
                ".agentic-pi/runtime/experience_retriever.py",
                str(run_dir),
                "--memory-dir",
                tmp,
            )
            self.assertEqual(retrieve.returncode, 0, retrieve.stdout)
            retrieved = load_json(run_dir / "retrieved_experience.json")
            self.assertFalse(retrieved["can_certify_done"])
            self.assertEqual(validate(retrieved, "retrieved_experience.schema.json"), [])

            score_result = run_python(".agentic-pi/runtime/strategy_scorer.py", str(run_dir))
            self.assertEqual(score_result.returncode, 0, score_result.stdout)
            scores = load_json(run_dir / "strategy_scores.json")
            by_id = {score["strategy_id"]: score for score in scores["scores"]}
            selector = run_python(".agentic-pi/runtime/strategy_selector.py", str(run_dir))
            self.assertEqual(selector.returncode, 0, selector.stdout)
            decision = load_json(run_dir / "strategy_decision.json")

        self.assertTrue(scores["experience_memory_used"])
        self.assertIn("success memory", " ".join(by_id["S.CODE_ARTIFACT_TEST"]["positive_factors"]))
        self.assertEqual(by_id["S.BLOCKED"]["score"], -99)
        self.assertEqual(by_id["S.BLOCKED"]["score_level"], "blocked")
        self.assertTrue(decision["advisory_memory_used"])
        self.assertEqual(decision["advisory_memory_authority"], "advisory_only")
        self.assertFalse(decision["advisory_memory_can_certify_done"])
        self.assertEqual(validate(decision, "strategy_decision.schema.json"), [])

    def test_schema_rejects_memory_claiming_certifier_authority(self):
        run_dir = self.make_completed_run("schema_false", "CERTIFIED_DONE")
        self.assertEqual(run_python(".agentic-pi/runtime/experience_extractor.py", str(run_dir)).returncode, 0)
        extract = load_json(run_dir / "experience_extract.json")
        extract["can_certify_done"] = True
        self.assertNotEqual(validate(extract, "experience_extract.schema.json"), [])

        record = {
            "learning_id": "L.BAD",
            "source_run_id": run_dir.name,
            "task_type": "coding",
            "strategy_id": "S.CODE_ARTIFACT_TEST",
            "outcome": "success",
            "outcome_status": "CERTIFIED_DONE",
            "principle": "bad",
            "do_not_use_when": [],
            "evidence_files": [],
            "created_at": "2026-05-07T00:00:00+00:00",
            "final_status_authority": "certifier_only",
            "can_certify_done": True,
        }
        self.assertNotEqual(validate(record, "learning_record.schema.json"), [])

        retrieved = {
            "run_id": run_dir.name,
            "generated_by": "test",
            "generated_at": "2026-05-07T00:00:00+00:00",
            "task_type": "coding",
            "matched_learning_ids": ["L.BAD"],
            "ignored_learning_ids": [],
            "strategy_adjustments": [
                {
                    "strategy_id": "S.CODE_ARTIFACT_TEST",
                    "score_delta": 1,
                    "reason": "bad",
                    "learning_id": "L.BAD",
                }
            ],
            "final_status_authority": "certifier_only",
            "can_certify_done": True,
        }
        self.assertNotEqual(validate(retrieved, "retrieved_experience.schema.json"), [])

    def test_strategy_scorer_rejects_unbounded_memory_delta(self):
        run_dir = self.make_completed_run("bad_delta", "NOT_DONE")
        write_json(
            run_dir / "strategy_applicability.json",
            {
                "run_id": run_dir.name,
                "task_type": "coding",
                "applicable_strategies": [strategy_candidate("S.CODE_ARTIFACT_TEST")],
                "blocked_strategies": [],
            },
        )
        write_json(
            run_dir / "retrieved_experience.json",
            {
                "run_id": run_dir.name,
                "generated_by": "test",
                "generated_at": "2026-05-07T00:00:00+00:00",
                "task_type": "coding",
                "matched_learning_ids": ["L.BAD"],
                "ignored_learning_ids": [],
                "strategy_adjustments": [
                    {
                        "strategy_id": "S.CODE_ARTIFACT_TEST",
                        "score_delta": 99,
                        "reason": "unbounded memory delta",
                        "learning_id": "L.BAD",
                    }
                ],
                "final_status_authority": "certifier_only",
                "can_certify_done": False,
            },
        )
        result = run_python(".agentic-pi/runtime/strategy_scorer.py", str(run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("retrieved_experience.json schema invalid", result.stdout)

    def test_memory_tools_do_not_write_status_artifacts(self):
        run_dir = self.make_completed_run("no_status_write", "CERTIFIED_DONE")
        for status_name in ["final_status.md", "policy_decision.json"]:
            status_path = run_dir / status_name
            if status_path.exists():
                status_path.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_python(".agentic-pi/runtime/experience_extractor.py", str(run_dir)).returncode, 0)
            self.assertEqual(
                run_python(
                    ".agentic-pi/runtime/learning_record_writer.py",
                    str(run_dir),
                    "--memory-dir",
                    tmp,
                ).returncode,
                0,
            )
            self.assertEqual(
                run_python(
                    ".agentic-pi/runtime/experience_retriever.py",
                    str(run_dir),
                    "--memory-dir",
                    tmp,
                ).returncode,
                0,
            )

        self.assertFalse((run_dir / "final_status.md").exists())
        self.assertTrue((run_dir / "certification.json").exists())
        self.assertFalse((run_dir / "policy_decision.json").exists())

    def test_v17_doc_locks_memory_boundary(self):
        doc = (ROOT / "docs" / "V1_7_EXPERIENCE_MEMORY.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("EXPERIENCE MEMORY IMPLEMENTED", doc)
        self.assertIn(".agentic-pi/runtime/experience_extractor.py", doc)
        self.assertIn(".agentic-pi/runtime/learning_record_writer.py", doc)
        self.assertIn(".agentic-pi/runtime/experience_retriever.py", doc)
        self.assertIn("memory can suggest", doc)
        self.assertIn("memory cannot certify DONE", doc)
        self.assertIn("v1.7 Experience Memory", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)


if __name__ == "__main__":
    unittest.main()
