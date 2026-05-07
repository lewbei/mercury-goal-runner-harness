import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
STATUS_FILES = ["final_status.md", "certification.json", "policy_decision.json"]


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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def goal_contract(run_id: str, raw_goal: str = "Create a Python CLI script for CSV summary") -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": raw_goal,
        "intent": raw_goal,
        "cleaned_goal": raw_goal,
        "final_outputs": ["tool.py"],
        "explicit_constraints": ["Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic workflow search."],
        "forbidden_actions": ["Do not certify DONE in workflow search artifacts."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "MEDIUM",
        "done_criteria": ["tool.py exists"],
        "failure_criteria": ["tool.py missing"],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": raw_goal,
    }


class WorkflowSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_schema_validator()

    def setUp(self):
        self.run_id = f"test_workflow_{self._testMethodName}"
        self.run_dir = RUN_ROOT / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        write_json(self.run_dir / "goal_contract.json", goal_contract(self.run_id))

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def prepare_domain_context(self):
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/domain_pack_selector.py",
        ]:
            result = run_python(tool, str(self.run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

    def run_search(self):
        result = run_python(".agentic-pi/runtime/workflow_search.py", str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)
        return load_json(self.run_dir / "workflow_search_trace.json")

    def test_workflow_search_writes_schema_valid_candidates_and_trace(self):
        self.prepare_domain_context()

        trace = self.run_search()

        candidates_doc = load_json(self.run_dir / "workflow_candidates.json")
        self.assertEqual(candidates_doc["run_id"], self.run_id)
        self.assertEqual(len(candidates_doc["candidates"]), 4)
        for candidate in candidates_doc["candidates"]:
            with self.subTest(candidate=candidate["workflow_id"]):
                self.assertEqual(self.validate_schema(candidate, "workflow_candidate.schema.json"), [])
                self.assertFalse(candidate["can_certify_done"])
                self.assertEqual(candidate["final_status_authority"], "certifier_only")
        self.assertEqual(self.validate_schema(trace, "workflow_search_trace.schema.json"), [])
        self.assertFalse(trace["can_certify_done"])

    def test_domain_workflow_is_selected_over_fixed_pipeline_when_pack_exists(self):
        self.prepare_domain_context()

        trace = self.run_search()

        self.assertEqual(trace["decision_status"], "SELECTED")
        self.assertEqual(trace["selected_workflow"], "W.DOMAIN_MEMORY_POLICY")
        selected = load_json(self.run_dir / "selected_workflow.json")
        self.assertEqual(selected["workflow_id"], "W.DOMAIN_MEMORY_POLICY")
        self.assertEqual(selected["domain_pack_used"], "coding")
        self.assertTrue(selected["uses_certifier"])

    def test_unsafe_workflows_are_rejected_with_reasons(self):
        self.prepare_domain_context()

        trace = self.run_search()

        reasons = {row["workflow_id"]: row["reason"] for row in trace["rejected_workflows"]}
        self.assertIn("false CERTIFIED_DONE risk too high", reasons["W.HIGH_FALSE_CERTIFIED_RISK"])
        self.assertIn("workflow bypasses certifier", reasons["W.UNSAFE_BYPASS_CERTIFIER"])
        self.assertIn("workflow writes status artifacts outside certifier", reasons["W.UNSAFE_BYPASS_CERTIFIER"])

    def test_fixed_pipeline_still_exists_as_safe_candidate(self):
        trace = self.run_search()
        candidates = load_json(self.run_dir / "workflow_candidates.json")["candidates"]
        by_id = {candidate["workflow_id"]: candidate for candidate in candidates}

        self.assertIn("W.FIXED_POLICY_PIPELINE", by_id)
        self.assertTrue(by_id["W.FIXED_POLICY_PIPELINE"]["uses_certifier"])
        self.assertFalse(by_id["W.FIXED_POLICY_PIPELINE"]["writes_status_artifacts"])
        self.assertEqual(trace["decision_status"], "SELECTED")

    def test_workflow_search_never_writes_status_artifacts(self):
        self.prepare_domain_context()

        self.run_search()

        for status_file in STATUS_FILES:
            self.assertFalse((self.run_dir / status_file).exists(), status_file)

    def test_v19_doc_locks_workflow_search_boundary(self):
        doc = (ROOT / "docs" / "V1_9_STRATEGY_SEARCH.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("STRATEGY SEARCH IMPLEMENTED", doc)
        self.assertIn("workflow_search_trace.json", doc)
        self.assertIn("workflow search cannot bypass certifier", doc)
        self.assertIn("workflow search cannot certify DONE", doc)
        self.assertIn("v1.9 Strategy Search / Workflow Optimization", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)


if __name__ == "__main__":
    unittest.main()
