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

    def write_planning_coverage_fixture(self, run_dir: Path, final_output: str = "artifacts/output.txt"):
        candidate = {
            "strategy_id": "S.WRITE_SIMPLE",
            "task_type": "writing",
            "required_capabilities": ["file_write_run_folder", "plan_graph", "policy_engine"],
            "expected_artifacts": [final_output],
            "verifier_requirements": ["independent content check required"],
            "risk_notes": ["polished but wrong"],
            "can_reach_certifying_evidence": True,
            "uses_artifact_tests": False,
            "needs_executable_behavior": False,
            "attempts_status_write": False,
            "attempts_verifier_forgery": False,
            "status_authority": "none",
            "risk_level": "LOW",
        }
        write_json(
            run_dir / "strategy_candidates.json",
            {"run_id": run_dir.name, "task_type": "writing", "candidates": [candidate]},
        )
        write_json(
            run_dir / "strategy_applicability.json",
            {"run_id": run_dir.name, "task_type": "writing", "applicable_strategies": [candidate], "blocked_strategies": []},
        )
        write_json(
            run_dir / "strategy_scores.json",
            {
                "run_id": run_dir.name,
                "task_type": "writing",
                "experience_memory_used": False,
                "scores": [
                    {
                        "strategy_id": "S.WRITE_SIMPLE",
                        "score": 7,
                        "score_level": "preferred",
                        "positive_factors": ["can_reach_certifying_evidence"],
                        "penalties": [],
                    }
                ],
            },
        )
        write_json(
            run_dir / "strategy_decision.json",
            {
                "run_id": run_dir.name,
                "decision_status": "SELECTED",
                "selected_strategy": "S.WRITE_SIMPLE",
                "reason": "Selected strategy has the best deterministic score and passed applicability checks.",
                "rejected_strategies": [],
                "selector_checks": ["strategy selector did not write certification status artifacts"],
                "status_artifacts_absent_before_selection": True,
                "advisory_memory_used": False,
                "advisory_memory_learning_ids": [],
                "advisory_memory_authority": "advisory_only",
                "advisory_memory_can_certify_done": False,
            },
        )
        write_json(
            run_dir / "selected_strategy.json",
            {
                "run_id": run_dir.name,
                "strategy_id": "S.WRITE_SIMPLE",
                "task_type": "writing",
                "required_capabilities": ["file_write_run_folder", "plan_graph", "policy_engine"],
                "expected_artifacts": [final_output],
                "verifier_requirements": ["independent content check required"],
                "risk_notes": ["polished but wrong"],
                "can_reach_certifying_evidence": True,
            },
        )
        write_json(run_dir / "rejected_strategies.json", {"run_id": run_dir.name, "rejected_strategies": []})
        write_json(
            run_dir / "expected_artifacts.json",
            {
                "schema_version": "expected_artifacts_v1",
                "run_id": run_dir.name,
                "phase": "PLANNING",
                "artifacts": [
                    {
                        "artifact_id": "A.FINAL_OUTPUT",
                        "expected_path": final_output,
                        "description": "Final planned output",
                        "required": True,
                        "allowed_writers": ["Engineer"],
                        "forbidden_writers": ["Reporter", "Critic", "Certifier"],
                        "success_criteria": [f"{final_output} exists"],
                        "min_size_bytes": 1,
                    }
                ],
            },
        )

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

    def test_adaptive_research_inputs_are_planning_only(self):
        run_dir = self.make_run("adaptive_research", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/adaptive_research_inputs.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        artifact = load_json(run_dir / "adaptive_research_inputs.json")
        self.assertFalse(artifact["authority"]["can_certify_done"])
        self.assertFalse(artifact["authority"]["can_write_status_artifacts"])
        self.assertFalse(artifact["authority"]["claim_correctness"])
        self.assertTrue(artifact["determinism_boundary"]["adaptive_generation_may_be_nondeterministic"])
        self.assertTrue(artifact["determinism_boundary"]["deterministic_validation_required"])
        self.assertTrue(artifact["determinism_boundary"]["validators_must_not_fetch_network"])
        self.assertTrue(artifact["determinism_boundary"]["certifier_ignores_as_authority"])
        self.assertTrue(all(not item["can_certify_done"] for item in artifact["findings"]))
        self.assertTrue(all(item["authority_impact"] == "none" for item in artifact["findings"]))
        self.assertTrue(all(not item["code_copied"] for item in artifact["findings"]))
        self.assertIn("final_status.json", artifact["status_artifact_write_policy"]["forbidden_paths"])
        self.assertFalse(artifact["status_artifact_write_policy"]["attempted_status_write"])

        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/adaptive_research_inputs.schema.json",
            str(run_dir / "adaptive_research_inputs.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)
        validator = run_python(".agentic-pi/validators/validate_adaptive_research_inputs.py", str(run_dir))
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_adaptive_research_inputs_reject_authority_claim(self):
        run_dir = self.make_run("adaptive_research_authority", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/adaptive_research_inputs.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        artifact = load_json(run_dir / "adaptive_research_inputs.json")
        artifact["authority"]["can_certify_done"] = True
        artifact["authority"]["can_write_status_artifacts"] = True
        artifact["authority"]["claim_correctness"] = True
        artifact["findings"][0]["authority_impact"] = "certifies"
        artifact["findings"][0]["can_certify_done"] = True
        artifact["findings"][0]["code_copied"] = True
        artifact["status_artifact_write_policy"]["attempted_status_write"] = True
        write_json(run_dir / "adaptive_research_inputs.json", artifact)

        validator = run_python(".agentic-pi/validators/validate_adaptive_research_inputs.py", str(run_dir))
        self.assertNotEqual(validator.returncode, 0, validator.stdout)
        self.assertIn("can_certify_done", validator.stdout)
        self.assertIn("claim_correctness", validator.stdout)
        self.assertIn("attempted_status_write", validator.stdout)

    def test_planning_artifacts_consume_adaptive_research_as_planning_only(self):
        run_dir = self.make_run("adaptive_research_planning", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/adaptive_research_inputs.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        result = run_python(".agentic-pi/runtime/planning_search_tree.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        result = run_python(".agentic-pi/runtime/planning_coverage.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        tree = load_json(run_dir / "planning_search_tree.json")
        self.assertIn("adaptive_autoresearch_provenance", {item["method_id"] for item in tree["method_influences"]})
        self.assertIn("live_adaptive_autoresearch_sampling", {item["method_id"] for item in tree["deferred_expansion_methods"]})
        self.assertTrue(any(node["node_id"] == "N.STRATEGY.ADAPTIVE_RESEARCH_INPUTS" for node in tree["nodes"]))
        self.assertFalse(tree["authority"]["can_certify_done"])

        coverage = load_json(run_dir / "planning_coverage.json")
        self.assertIn("adaptive_autoresearch_input_recording", coverage["search_budget"]["search_methods_considered"])
        self.assertTrue(any(item["option_id"] == "A.ADAPTIVE_RESEARCH_INPUTS" for item in coverage["alternatives_considered"]))
        self.assertFalse(coverage["authority"]["can_certify_done"])

        self.assertEqual(run_python(".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir)).returncode, 0)
        self.assertEqual(run_python(".agentic-pi/validators/validate_planning_coverage.py", str(run_dir)).returncode, 0)

    def test_planning_search_tree_records_deep_bounded_path(self):
        run_dir = self.make_run("planning_tree", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_search_tree.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        tree = load_json(run_dir / "planning_search_tree.json")
        self.assertFalse(tree["authority"]["can_certify_done"])
        self.assertFalse(tree["authority"]["claim_exhaustive_search"])
        self.assertFalse(tree["authority"]["claim_correctness"])
        self.assertFalse(tree["proof_boundary"]["proves_all_possible_plans"])
        self.assertFalse(tree["proof_boundary"]["proves_artifact_correctness"])
        self.assertTrue(tree["proof_boundary"]["requires_verifier_artifacts"])
        self.assertEqual(tree["implementation_boundary"]["source_code_origin"], "harness_native_no_vendor_copy")
        self.assertFalse(tree["implementation_boundary"]["planner_can_certify_done"])
        self.assertEqual(tree["search_config"]["completeness_claim"], "bounded_not_exhaustive")
        self.assertEqual(tree["search_config"]["correctness_claim"], "not_proven_by_planning")
        self.assertGreaterEqual(tree["coverage_metrics"]["max_depth_reached"], 4)
        self.assertGreaterEqual(tree["coverage_metrics"]["selected_path_length"], 4)
        self.assertGreaterEqual(tree["coverage_metrics"]["pruned_or_deferred_count"], 1)
        self.assertGreaterEqual(tree["coverage_metrics"]["iterations_recorded"], 3)
        self.assertGreaterEqual(tree["coverage_metrics"]["deferred_expansion_method_count"], 3)
        self.assertEqual(tree["coverage_metrics"]["candidate_evaluation_count"], tree["coverage_metrics"]["candidate_strategy_count"])
        self.assertEqual(tree["search_config"]["max_rollouts"], 0)
        self.assertFalse(tree["search_config"]["mcts_optimality_claim"])
        self.assertFalse(tree["operation_graph"]["can_certify_done"])
        self.assertIn("lats_mcts", {item["method_id"] for item in tree["method_influences"]})
        self.assertIn(
            "mcts_rollout_backpropagation",
            {item["method_id"] for item in tree["deferred_expansion_methods"]},
        )
        self.assertIn("score_strategy_frontier", {item["phase"] for item in tree["search_iterations"]})
        self.assertTrue(all(node["score_components"]["total"] == node["score"] for node in tree["nodes"]))
        self.assertTrue(any(node["planned_evidence_refs"] for node in tree["nodes"]))
        self.assertEqual(tree["candidate_evaluations"][0]["strategy_id"], "S.WRITE_SIMPLE")

        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/planning_search_tree.schema.json",
            str(run_dir / "planning_search_tree.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)
        validator = run_python(".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir))
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_planning_search_tree_rejects_exhaustive_or_authority_claim(self):
        run_dir = self.make_run("planning_tree_authority", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_search_tree.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        tree = load_json(run_dir / "planning_search_tree.json")
        tree["authority"]["can_certify_done"] = True
        tree["authority"]["claim_exhaustive_search"] = True
        tree["authority"]["claim_correctness"] = True
        tree["proof_boundary"]["proves_all_possible_plans"] = True
        tree["proof_boundary"]["proves_artifact_correctness"] = True
        write_json(run_dir / "planning_search_tree.json", tree)

        validator = run_python(".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir))
        self.assertNotEqual(validator.returncode, 0, validator.stdout)
        self.assertIn("can_certify_done", validator.stdout)
        self.assertIn("claim_correctness", validator.stdout)
        self.assertIn("proves_artifact_correctness", validator.stdout)

    def test_planning_search_tree_rejects_budget_overrun(self):
        run_dir = self.make_run("planning_tree_budget", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_search_tree.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        tree = load_json(run_dir / "planning_search_tree.json")
        tree["search_config"]["max_nodes"] = tree["coverage_metrics"]["nodes_expanded"] - 1
        write_json(run_dir / "planning_search_tree.json", tree)

        validator = run_python(".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir))
        self.assertNotEqual(validator.returncode, 0, validator.stdout)
        self.assertIn("max_nodes", validator.stdout)

    def test_planning_search_tree_records_need_user_stop_branch(self):
        run_dir = self.make_run("planning_tree_need_user", "blue sky purpose with no operational keyword")
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)
        selector = run_python(".agentic-pi/runtime/strategy_selector.py", str(run_dir))
        self.assertNotEqual(selector.returncode, 0, selector.stdout)

        result = run_python(".agentic-pi/runtime/planning_search_tree.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        tree = load_json(run_dir / "planning_search_tree.json")
        selected_nodes = [node for node in tree["nodes"] if node["status"] == "need_user"]
        self.assertTrue(selected_nodes)
        self.assertIn("N.STOP.NEED_USER_STRATEGY", tree["selected_path"])
        validator = run_python(".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir))
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_planning_coverage_records_bounded_alternatives(self):
        run_dir = self.make_run("planning_coverage", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_coverage.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        coverage = load_json(run_dir / "planning_coverage.json")
        self.assertFalse(coverage["authority"]["can_certify_done"])
        self.assertFalse(coverage["authority"]["claim_exhaustive_planning"])
        self.assertFalse(coverage["authority"]["claim_correctness"])
        self.assertFalse(coverage["proof_boundary"]["proves_all_possible_plans"])
        self.assertFalse(coverage["proof_boundary"]["proves_artifact_correctness"])
        self.assertTrue(coverage["proof_boundary"]["requires_certifier"])
        self.assertEqual(coverage["search_budget"]["search_completeness_claim"], "bounded_not_exhaustive")
        self.assertGreaterEqual(len(coverage["alternatives_considered"]), 2)
        self.assertIn("lats_style_deferred_rollout_record", coverage["search_budget"]["search_methods_considered"])
        self.assertTrue(any("Language Agent Tree Search" in item["source_title"] for item in coverage["research_basis"]))

        schema = run_python(
            ".agentic-pi/validators/validate_schema.py",
            ".agentic-pi/schemas/planning_coverage.schema.json",
            str(run_dir / "planning_coverage.json"),
        )
        self.assertEqual(schema.returncode, 0, schema.stdout)
        validator = run_python(".agentic-pi/validators/validate_planning_coverage.py", str(run_dir))
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_planning_coverage_rejects_authority_claim(self):
        run_dir = self.make_run("planning_authority", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_coverage.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        coverage = load_json(run_dir / "planning_coverage.json")
        coverage["authority"]["can_certify_done"] = True
        coverage["authority"]["claim_correctness"] = True
        coverage["proof_boundary"]["proves_artifact_correctness"] = True
        write_json(run_dir / "planning_coverage.json", coverage)

        validator = run_python(".agentic-pi/validators/validate_planning_coverage.py", str(run_dir))
        self.assertNotEqual(validator.returncode, 0, validator.stdout)
        self.assertIn("can_certify_done", validator.stdout)
        self.assertIn("claim_correctness", validator.stdout)
        self.assertIn("proves_artifact_correctness", validator.stdout)

    def test_planning_coverage_rejects_missing_non_selected_branch(self):
        run_dir = self.make_run("planning_branch", "Write a README.md document")
        self.write_planning_coverage_fixture(run_dir)
        result = run_python(".agentic-pi/runtime/planning_coverage.py", str(run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

        coverage = load_json(run_dir / "planning_coverage.json")
        coverage["alternatives_considered"] = [
            item for item in coverage["alternatives_considered"] if item["status"] == "selected"
        ]
        coverage["search_budget"]["rejected_or_deferred_count"] = 0
        write_json(run_dir / "planning_coverage.json", coverage)

        validator = run_python(".agentic-pi/validators/validate_planning_coverage.py", str(run_dir))
        self.assertNotEqual(validator.returncode, 0, validator.stdout)
        self.assertIn("alternatives_considered", validator.stdout)

    def test_planning_artifacts_alone_do_not_prove_correctness(self):
        run_dir = self.make_run("planning_not_correctness", "Write a README.md document", "README.md")
        roadmap = run_python(".agentic-pi/runtime/roadmap_planner.py", "--run-id", run_dir.name, "--stop-after", "plan_graph")
        self.assertEqual(roadmap.returncode, 0, roadmap.stdout)
        self.assertTrue((run_dir / "adaptive_research_inputs.json").is_file())
        self.assertTrue((run_dir / "planning_search_tree.json").is_file())
        self.assertTrue((run_dir / "planning_coverage.json").is_file())

        full_verify = run_python(".agentic-pi/runtime/full_verify.py", str(run_dir))
        self.assertNotEqual(full_verify.returncode, 0, full_verify.stdout)
        self.assertIn("missing required proof artifact: verifier_contract.json", full_verify.stdout)
        self.assertIn("missing required proof artifact: verifier_artifacts/*.json", full_verify.stdout)
        self.assertIn("FINAL: NOT_DONE", full_verify.stdout)
        for status_name in ["final_status.md", "certification.json", "policy_decision.json"]:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_goal_run_uses_strict_roadmap_planning_artifacts(self):
        run_id = f"pi_smoke_goal_run_{self._testMethodName}"
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
        run_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-run",
            run_id,
            "--skip-memory-update",
        )
        self.assertEqual(run_result.returncode, 0, run_result.stdout)

        for artifact_name in [
            "adaptive_research_inputs.json",
            "planning_search_tree.json",
            "planning_coverage.json",
            "expected_artifacts.json",
            "macro_plan.json",
            "vertical_slice_candidates.json",
            "vertical_slice_selection.json",
            "selected_plan.json",
            "merged_plan.json",
            "plan_graph.json",
            "validator_certification.json",
        ]:
            self.assertTrue((run_dir / artifact_name).is_file(), artifact_name)
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "CERTIFIED_DONE")
        self.assertEqual(load_json(run_dir / "policy_decision.json")["status"], "CERTIFIED_DONE")
        self.assertFalse(load_json(run_dir / "planning_search_tree.json")["authority"]["can_certify_done"])

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
