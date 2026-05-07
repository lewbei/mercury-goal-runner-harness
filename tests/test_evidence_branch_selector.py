import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
BRANCH_GENERATOR = ROOT / ".agentic-pi" / "runtime" / "branch_generator.py"
SELECTOR = ROOT / ".agentic-pi" / "runtime" / "evidence_branch_selector.py"


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def goal_contract(run_id: str):
    return {
        "run_id": run_id,
        "raw_user_prompt": "evidence selector test",
        "intent": "evidence selector test",
        "cleaned_goal": "select branch by certifiability",
        "final_outputs": ["artifacts/output.txt"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": ["Do not certify from selector output."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "HARD",
        "done_criteria": ["output exists"],
        "failure_criteria": ["output missing"],
        "ask_user_conditions": [],
        "max_steps": 3,
        "execution_prompt": "select branch",
    }


class EvidenceBranchSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_module(
            "validate_schema_for_evidence_selector_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )

    def setUp(self):
        self.run_id = f"test_evidence_selector_{self._testMethodName}"
        self.run_dir = RUN_ROOT / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        write_json(self.run_dir / "goal_contract.json", goal_contract(self.run_id))
        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def test_selector_selects_certifiable_branch(self):
        result = run_python(str(SELECTOR), str(self.run_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        decision = load_json(self.run_dir / "branch_decision.json")
        self.assertEqual(decision["decision_status"], "SELECTED")
        self.assertEqual(decision["selected_branch"], "B.MINIMAL")
        self.assertIn("P2/P3 certifying", decision["reason"])
        self.assertEqual(self.validate_schema(decision, "branch_decision.schema.json"), [])
        self.assertTrue((self.run_dir / "selected_branch.json").is_file())
        self.assertTrue((self.run_dir / "rejected_branches.json").is_file())
        self.assertTrue((self.run_dir / "selector_audit.json").is_file())
        self.assertFalse((self.run_dir / "final_status.md").exists())
        self.assertFalse((self.run_dir / "certification.json").exists())
        self.assertFalse((self.run_dir / "policy_decision.json").exists())

    def test_selector_requests_user_verifier_when_no_branch_is_certifiable(self):
        manifest = load_json(self.run_dir / "branch_manifest.json")
        for row in manifest["branches"]:
            candidate_path = self.run_dir / row["branch_candidate_path"]
            candidate = load_json(candidate_path)
            candidate["verifier_requirements"] = ["P1 visible evidence only"]
            write_json(candidate_path, candidate)

        result = run_python(str(SELECTOR), str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        decision = load_json(self.run_dir / "branch_decision.json")
        self.assertEqual(decision["decision_status"], "NEED_USER_VERIFIER")
        self.assertEqual(decision["selected_branch"], "")
        self.assertEqual(len(decision["rejected_branches"]), 3)
        self.assertEqual(self.validate_schema(decision, "branch_decision.schema.json"), [])
        self.assertFalse((self.run_dir / "final_status.md").exists())
        self.assertFalse((self.run_dir / "certification.json").exists())
        self.assertFalse((self.run_dir / "policy_decision.json").exists())

    def test_selector_fails_closed_on_invalid_branch_set(self):
        registry_path = self.run_dir / "branches" / "B.MINIMAL" / "artifact_registry.json"
        registry = load_json(registry_path)
        registry["artifacts"][0]["path"] = "../escape.txt"
        write_json(registry_path, registry)

        result = run_python(str(SELECTOR), str(self.run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        decision = load_json(self.run_dir / "branch_decision.json")
        self.assertEqual(decision["decision_status"], "NO_CERTIFIABLE_BRANCH")
        self.assertIn("failed validation", decision["reason"])


if __name__ == "__main__":
    unittest.main()
