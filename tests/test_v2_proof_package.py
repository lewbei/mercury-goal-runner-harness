import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs"
MATRIX_PATH = ROOT / ".agentic-pi" / "proof_matrix" / "proof_matrix.json"


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


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V2ProofPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_schema_validator()

    def tearDown(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def test_proof_matrix_schema_validates_and_contains_required_claims(self):
        matrix = load_json(MATRIX_PATH)

        self.assertEqual(self.validate_schema(matrix, "proof_matrix.schema.json"), [])
        claim_ids = {entry["claim_id"] for entry in matrix["entries"]}
        for claim_id in [
            "final_status_json_authority",
            "evidence_freeze",
            "run_local_quarantine_memory",
            "quarantine_memory",
            "mempalace_card_governance",
            "mempalace_context_pack",
            "ace_reflector_curator",
            "ace_memory_write_gate",
            "domain_packs",
            "workflow_search",
            "diagnostic_evaluation",
            "trajectory_evaluation",
            "local_harness_helper_help",
            "direct_pi_mercury_behavior",
            "real_pi_interactive_smoke_docs",
            "real_pi_session_monitor",
            "real_pi_session_trace_capture",
            "agentic_autonomy_probe",
            "agentic_negative_probes",
            "live_negative_prompt_capture",
            "real_pi_behavior_evaluation",
            "real_pi_prompt_coverage_matrix",
            "adversarial_red_team_loop",
            "runtime_enforcement",
            "rpg_test_record",
            "rpg_test_aggregation",
            "stage2_finalisation_gate",
            "stage3_runtime_readiness_gate",
            "stage3_runtime_preflight_gate",
            "guarded_runtime_smoke",
            "guarded_execution_v1",
            "planning_efficiency_v2_preflight",
            "planning_efficiency_v2_1_hardening",
            "planning_efficiency_v2_2_cleanup",
            "planning_efficiency_v3_repair_loop",
            "guarded_execution_v2",
            "guarded_execution_v3",
            "planning_efficiency_v1",
            "full_unittest",
            "benchmark",
        ]:
            self.assertIn(claim_id, claim_ids)
        self.assertTrue(any(entry["mode"] == "full" for entry in matrix["entries"]))

    def test_quick_proof_runner_writes_schema_valid_result(self):
        result = run_python(".agentic-pi/runtime/run_proof_matrix.py", "--mode", "quick")

        self.assertEqual(result.returncode, 0, result.stdout)
        result_path = OUTPUT_DIR / "proof_matrix_result.json"
        self.assertTrue(result_path.is_file())
        proof_result = load_json(result_path)
        self.assertEqual(self.validate_schema(proof_result, "proof_matrix_result.schema.json"), [])
        self.assertEqual(proof_result["mode"], "quick")
        self.assertTrue(proof_result["all_passed"])
        self.assertFalse(proof_result["can_certify_done"])
        self.assertEqual(proof_result["final_status_authority"], "certifier_only")
        claim_ids = {entry["claim_id"] for entry in proof_result["entries"]}
        self.assertIn("final_status_json_authority", claim_ids)
        self.assertIn("evidence_freeze", claim_ids)
        self.assertIn("run_local_quarantine_memory", claim_ids)
        self.assertIn("quarantine_memory", claim_ids)
        self.assertIn("mempalace_card_governance", claim_ids)
        self.assertIn("mempalace_context_pack", claim_ids)
        self.assertIn("ace_reflector_curator", claim_ids)
        self.assertIn("ace_memory_write_gate", claim_ids)
        self.assertIn("domain_packs", claim_ids)
        self.assertIn("workflow_search", claim_ids)
        self.assertIn("direct_pi_mercury_behavior", claim_ids)
        self.assertIn("real_pi_interactive_smoke_docs", claim_ids)
        self.assertIn("real_pi_session_monitor", claim_ids)
        self.assertIn("real_pi_session_trace_capture", claim_ids)
        self.assertIn("agentic_autonomy_probe", claim_ids)
        self.assertIn("agentic_negative_probes", claim_ids)
        self.assertIn("live_negative_prompt_capture", claim_ids)
        self.assertIn("real_pi_behavior_evaluation", claim_ids)
        self.assertIn("real_pi_prompt_coverage_matrix", claim_ids)
        self.assertIn("adversarial_red_team_loop", claim_ids)
        self.assertIn("runtime_enforcement", claim_ids)
        self.assertIn("rpg_test_record", claim_ids)
        self.assertIn("rpg_test_aggregation", claim_ids)
        self.assertIn("stage2_finalisation_gate", claim_ids)
        self.assertIn("stage3_runtime_readiness_gate", claim_ids)
        self.assertIn("stage3_runtime_preflight_gate", claim_ids)
        self.assertIn("guarded_runtime_smoke", claim_ids)
        self.assertIn("guarded_execution_v1", claim_ids)
        self.assertIn("planning_efficiency_v2_preflight", claim_ids)
        self.assertIn("planning_efficiency_v2_1_hardening", claim_ids)
        self.assertIn("planning_efficiency_v2_2_cleanup", claim_ids)
        self.assertIn("planning_efficiency_v3_repair_loop", claim_ids)
        self.assertIn("guarded_execution_v2", claim_ids)
        self.assertIn("guarded_execution_v3", claim_ids)
        self.assertIn("planning_efficiency_v1", claim_ids)
        self.assertNotIn("benchmark", claim_ids)

    def test_quick_proof_runner_outputs_only_under_agentic_runs(self):
        result = run_python(".agentic-pi/runtime/run_proof_matrix.py", "--mode", "quick")

        self.assertEqual(result.returncode, 0, result.stdout)
        for path in [
            OUTPUT_DIR / "proof_matrix_result.json",
            OUTPUT_DIR / "diagnostic" / "diagnostic_metrics.json",
            OUTPUT_DIR / "trajectory" / "trajectory_metrics.json",
            OUTPUT_DIR / "stage2_finalisation_gate_report_v1.json",
            OUTPUT_DIR / "stage3_runtime_readiness_report_v1.json",
            OUTPUT_DIR / "stage3_runtime_preflight_report_v1.json",
            OUTPUT_DIR / "guarded_runtime_smoke_report_v1.json",
            OUTPUT_DIR / "guarded_execution_v1_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_preflight_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_compile_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_lint_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_plan.json",
            OUTPUT_DIR / "planning_efficiency_v2_expected_artifacts.json",
            OUTPUT_DIR / "planning_efficiency_v2_1_hardening_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_1_hardening" / "planning_efficiency_v2_preflight_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_2_cleanup_report.json",
            OUTPUT_DIR / "planning_efficiency_v2_2_cleanup" / "stage3_runtime_preflight_report_v1.json",
            OUTPUT_DIR / "planning_efficiency_v2_2_cleanup" / "planning_efficiency_v2_preflight_report.json",
            OUTPUT_DIR / "planning_efficiency_v3_repair_report.json",
            OUTPUT_DIR / "planning_efficiency_v3_repair_loop" / "planning_efficiency_v3_repaired_goal.json",
            OUTPUT_DIR / "planning_efficiency_v3_repair_loop" / "planning_efficiency_v3_preflight_report.json",
            OUTPUT_DIR / "planning_efficiency_v3_repair_loop" / "planning_efficiency_v3_plan.json",
            OUTPUT_DIR / "planning_efficiency_v3_repair_loop" / "planning_efficiency_v3_expected_artifacts.json",
            OUTPUT_DIR / "guarded_execution_v2_report.json",
            OUTPUT_DIR / "guarded_execution_v2_ledger.json",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v1" / "artifacts" / "guarded_execution_v1_note.txt",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v2" / "artifacts" / "planning_efficiency_v3_summary.txt",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v2" / "artifacts" / "planning_efficiency_v3_observation.txt",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v2" / "artifacts" / "planning_efficiency_v3_boundary.txt",
            OUTPUT_DIR / "guarded_execution_v3_report.json",
            OUTPUT_DIR / "guarded_execution_v3_ledger.json",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v3" / "artifacts" / "guarded_execution_v3_repair_request.json",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v3" / "artifacts" / "guarded_execution_v3_summary.txt",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v3" / "artifacts" / "guarded_execution_v3_observation.txt",
            ROOT / ".agentic-runs" / "proof_matrix_guarded_execution_v3" / "artifacts" / "guarded_execution_v3_boundary.txt",
            OUTPUT_DIR / "planning_efficiency_v1_compile_report.json",
            OUTPUT_DIR / "planning_efficiency_v1_lint_report.json",
            OUTPUT_DIR / "planning_efficiency_v1_plan.json",
            OUTPUT_DIR / "planning_efficiency_v1_expected_artifacts.json",
        ]:
            self.assertTrue(path.is_file(), path)
            self.assertIn(".agentic-runs", path.as_posix())

    def test_v20_docs_lock_integrated_proof_boundary(self):
        doc = (ROOT / "docs" / "V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md").read_text(encoding="utf-8")
        examples = (ROOT / "docs" / "V2_0_EXAMPLES.md").read_text(encoding="utf-8")

        self.assertIn("INTEGRATED HARNESS PROOF PACKAGE IMPLEMENTED", doc)
        self.assertIn("proof_matrix_result.json", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("The full Pi goal-runner chain is autonomously verified", doc)
        self.assertIn("DONE_PASS", examples)
        self.assertIn("PROVISIONAL_DONE", examples)
        self.assertIn("CERTIFIED_DONE", examples)
        self.assertIn("NOT_DONE", examples)
        self.assertIn("workflow search", examples)
        self.assertIn("Final status still comes only from", examples)


if __name__ == "__main__":
    unittest.main()
