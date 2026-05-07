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


def goal_contract(run_id: str, raw_goal: str, final_output: str = "artifacts/output.txt") -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": raw_goal,
        "intent": raw_goal,
        "cleaned_goal": raw_goal,
        "final_outputs": [final_output],
        "explicit_constraints": ["Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic strategy planner proof."],
        "forbidden_actions": ["Do not certify DONE in planner artifacts."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "SIMPLE",
        "done_criteria": [f"{final_output} exists."],
        "failure_criteria": [f"{final_output} missing."],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": raw_goal,
    }


def verifier_contract(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "target_goal": "Verifier contract for strategy proof fixture.",
        "target_artifacts": ["README.md"],
        "required_verifier_level": "P2",
        "allow_self_generated_only": False,
        "required_behaviors": ["README.md exists", "README.md contains the word harness"],
        "forbidden_verifier_patterns": ["same worker self-test", "file existence only"],
        "minimum_strength_level": "certifying",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"],
    }


class StrategyPlannerTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def make_run(self, suffix: str, raw_goal: str, final_output: str = "artifacts/output.txt") -> Path:
        run_id = f"test_strategy_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        write_json(run_dir / "goal_contract.json", goal_contract(run_id, raw_goal, final_output))
        (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
        return run_dir

    def test_task_type_router_classifies_core_task_types(self):
        cases = [
            ("writing", "Write a README.md document for the harness", "README.md"),
            ("coding", "Create a Python CLI script for CSV summary", "tool.py"),
            ("debugging", "Fix the failing traceback in the CLI", "artifacts/patch.md"),
            ("benchmark", "Create a diagnostic benchmark with false pass metrics", "artifacts/report.md"),
            ("unknown", "blue sky purpose with no operational keyword", "artifacts/output.txt"),
        ]
        for expected, raw_goal, final_output in cases:
            with self.subTest(expected=expected):
                run_dir = self.make_run(expected, raw_goal, final_output)
                result = run_python(".agentic-pi/runtime/task_type_router.py", str(run_dir))
                self.assertEqual(result.returncode, 0, result.stdout)
                decision = load_json(run_dir / "task_type_decision.json")
                self.assertEqual(decision["task_type"], expected)
                schema = run_python(
                    ".agentic-pi/validators/validate_schema.py",
                    ".agentic-pi/schemas/task_type_decision.schema.json",
                    str(run_dir / "task_type_decision.json"),
                )
                self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_capability_inventory_contains_required_capabilities(self):
        run_dir = self.make_run("capabilities", "Write a README.md document", "README.md")
        result = run_python(".agentic-pi/runtime/capability_inventory.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        inventory = load_json(run_dir / "capability_inventory.json")
        capability_ids = {capability["capability_id"] for capability in inventory["capabilities"]}
        for capability_id in [
            "python_command",
            "artifact_test",
            "plan_graph",
            "policy_engine",
            "audit",
            "replay",
            "rollback_dry_run",
        ]:
            self.assertIn(capability_id, capability_ids)
        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/capability_inventory.schema.json",
            str(run_dir / "capability_inventory.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_strategy_generator_emits_expected_strategies(self):
        cases = [
            ("writing", "Write a README.md document", "README.md", "S.WRITE_SIMPLE"),
            ("coding", "Create a Python CLI script for CSV summary", "tool.py", "S.CODE_ARTIFACT_TEST"),
            ("debugging", "Fix a failing traceback", "artifacts/patch.md", "S.DEBUG_REPRO_THEN_PATCH"),
            ("benchmark", "Create diagnostic benchmark metrics", "artifacts/report.md", "S.BENCHMARK_DIAGNOSTIC"),
            ("unknown", "blue sky purpose with no operational keyword", "artifacts/output.txt", "S.UNKNOWN_NEED_USER"),
        ]
        for suffix, raw_goal, final_output, expected_strategy in cases:
            with self.subTest(expected_strategy=expected_strategy):
                run_dir = self.make_run(suffix, raw_goal, final_output)
                for tool in [
                    ".agentic-pi/runtime/task_type_router.py",
                    ".agentic-pi/runtime/strategy_generator.py",
                ]:
                    result = run_python(tool, str(run_dir))
                    self.assertEqual(result.returncode, 0, result.stdout)
                candidates = load_json(run_dir / "strategy_candidates.json")
                strategy_ids = {candidate["strategy_id"] for candidate in candidates["candidates"]}
                self.assertIn(expected_strategy, strategy_ids)
                candidate_path = run_dir / "candidate_for_schema.json"
                write_json(candidate_path, candidates["candidates"][0])
                schema = run_python(
                    ".agentic-pi/validators/validate_schema.py",
                    ".agentic-pi/schemas/strategy_candidate.schema.json",
                    str(candidate_path),
                )
                self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_applicability_gate_blocks_forbidden_status_write_and_missing_capability(self):
        run_dir = self.make_run("blocked", "Create a Python CLI script", "tool.py")
        write_json(
            run_dir / "capability_inventory.json",
            {
                "run_id": run_dir.name,
                "capabilities": [
                    {
                        "capability_id": "file_write_run_folder",
                        "description": "write files in run folder",
                        "can_write_files": True,
                        "writes_status_artifacts": False,
                        "certifier_owned": False,
                        "allowed_for_task_types": ["*"],
                    }
                ],
            },
        )
        write_json(
            run_dir / "strategy_candidates.json",
            {
                "run_id": run_dir.name,
                "task_type": "coding",
                "candidates": [
                    {
                        "strategy_id": "S.BAD_STATUS_WRITE",
                        "task_type": "coding",
                        "description": "bad strategy",
                        "required_capabilities": ["file_write_run_folder"],
                        "expected_artifacts": ["tool.py"],
                        "verifier_requirements": ["P2 verifier"],
                        "risk_notes": ["tries to write status"],
                        "can_reach_certifying_evidence": True,
                        "uses_artifact_tests": True,
                        "needs_executable_behavior": True,
                        "attempts_status_write": True,
                        "attempts_verifier_forgery": False,
                        "status_authority": "none",
                        "risk_level": "HIGH",
                    },
                    {
                        "strategy_id": "S.MISSING_CAPABILITY",
                        "task_type": "coding",
                        "description": "missing capability strategy",
                        "required_capabilities": ["missing_tool"],
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
                    },
                ],
            },
        )

        result = run_python(".agentic-pi/runtime/strategy_applicability_gate.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        blocked = load_json(run_dir / "strategy_applicability.json")["blocked_strategies"]
        reasons = {row["strategy_id"]: " ".join(row["block_reasons"]) for row in blocked}
        self.assertIn("strategy attempts manual status artifact write", reasons["S.BAD_STATUS_WRITE"])
        self.assertIn("missing capability: missing_tool", reasons["S.MISSING_CAPABILITY"])

    def test_strategy_scorer_ranks_certifiable_strategy_higher(self):
        run_dir = self.make_run("scorer", "Create a Python CLI script for CSV summary", "tool.py")
        write_json(run_dir / "verifier_contract.json", verifier_contract(run_dir.name))
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

        scores = load_json(run_dir / "strategy_scores.json")["scores"]
        by_id = {score["strategy_id"]: score for score in scores}
        self.assertGreaterEqual(by_id["S.CODE_ARTIFACT_TEST"]["score"], 7)
        self.assertEqual(by_id["S.CODE_ARTIFACT_TEST"]["score_level"], "preferred")

    def test_strategy_selector_is_deterministic_and_writes_no_status_artifacts(self):
        run_dir = self.make_run("selector", "Write a README.md document", "README.md")
        write_json(run_dir / "verifier_contract.json", verifier_contract(run_dir.name))
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

        decision = load_json(run_dir / "strategy_decision.json")
        self.assertEqual(decision["decision_status"], "SELECTED")
        self.assertEqual(decision["selected_strategy"], "S.WRITE_SIMPLE")
        self.assertTrue(decision["status_artifacts_absent_before_selection"])
        self.assertFalse(decision["advisory_memory_used"])
        self.assertEqual(decision["advisory_memory_authority"], "advisory_only")
        self.assertFalse(decision["advisory_memory_can_certify_done"])
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)
        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/strategy_decision.schema.json",
            str(run_dir / "strategy_decision.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)

    def test_step_compiler_writes_valid_merged_plan(self):
        run_dir = self.make_run("compiler", "Write a README.md document", "README.md")
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
            ".agentic-pi/runtime/strategy_selector.py",
            ".agentic-pi/runtime/step_compiler.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

        merged_plan = load_json(run_dir / "merged_plan.json")
        self.assertEqual(merged_plan["planner"], "step-compiler-v1.3")
        self.assertEqual(merged_plan["selected_strategy"], "S.WRITE_SIMPLE")
        self.assertEqual(merged_plan["steps"][0]["produces"][0]["artifact_id"], "A.FINAL_OUTPUT")
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_strategy_proof_reaches_certified_done_for_p2_fixture(self):
        run_id = f"pi_smoke_strategy_{self._testMethodName}"
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
        proof_result = run_python(".agentic-pi/runtime/pi_cli.py", "goal-strategy-proof", run_id)
        self.assertEqual(proof_result.returncode, 0, proof_result.stdout)

        self.assertEqual(load_json(run_dir / "task_type_decision.json")["task_type"], "writing")
        self.assertEqual(load_json(run_dir / "strategy_decision.json")["decision_status"], "SELECTED")
        self.assertEqual(load_json(run_dir / "selected_strategy.json")["strategy_id"], "S.WRITE_SIMPLE")
        self.assertEqual(load_json(run_dir / "merged_plan.json")["planner"], "step-compiler-v1.3")
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "CERTIFIED_DONE")
        self.assertEqual(load_json(run_dir / "policy_decision.json")["status"], "CERTIFIED_DONE")
        proof = load_json(run_dir / "strategy_proof.json")
        self.assertEqual(proof["final_status"], "CERTIFIED_DONE")
        self.assertEqual(proof["final_status_source"], "certification.json")

    def test_unknown_strategy_does_not_fake_done(self):
        run_dir = self.make_run("unknown_proof", "blue sky purpose with no operational keyword")
        result = run_python(".agentic-pi/runtime/strategy_proof_runner.py", run_dir.name)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(load_json(run_dir / "strategy_decision.json")["decision_status"], "NEED_USER_STRATEGY")
        self.assertEqual(load_json(run_dir / "strategy_proof.json")["final_status"], "NEED_USER_STRATEGY")
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_v13_doc_locks_boundary(self):
        doc = (ROOT / "docs" / "V1_3_STRATEGY_PLANNER.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("STRATEGY PLANNER IMPLEMENTED", doc)
        self.assertIn("does not prove", doc.lower())
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("v1.4 Milestone Planning", roadmap)
        self.assertIn("v2.0 Integrated Harness Proof Package", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)


if __name__ == "__main__":
    unittest.main()
