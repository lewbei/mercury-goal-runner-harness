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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def goal_contract(run_id: str, complexity="HARD"):
    return {
        "run_id": run_id,
        "raw_user_prompt": "branch generation test",
        "intent": "branch generation test",
        "cleaned_goal": "create branch candidates",
        "final_outputs": ["artifacts/output.txt"],
        "explicit_constraints": [],
        "inferred_constraints": [],
        "forbidden_actions": ["Do not touch verifier artifacts."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": complexity,
        "done_criteria": ["output exists"],
        "failure_criteria": ["output missing"],
        "ask_user_conditions": [],
        "max_steps": 3,
        "execution_prompt": "generate branches",
    }


class BranchGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.branch_generator = load_module("branch_generator_for_tests", BRANCH_GENERATOR)
        cls.validator = load_module(
            "validate_schema_for_branch_generation_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )

    def setUp(self):
        self.run_id = f"test_branch_generation_{self._testMethodName}"
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

    def generate(self):
        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_hard_goal_generates_three_candidate_branches(self):
        self.generate()
        manifest = load_json(self.run_dir / "branch_manifest.json")

        self.assertEqual([row["branch_id"] for row in manifest["branches"]], ["B.MINIMAL", "B.ROBUST", "B.SKEPTIC"])
        self.assertEqual(self.validate_schema(manifest, "branch_manifest.schema.json"), [])
        for row in manifest["branches"]:
            candidate = load_json(self.run_dir / row["branch_candidate_path"])
            self.assertEqual(candidate["selection_state"], "candidate")
            self.assertNotIn(candidate["selection_state"], {"DONE_PASS", "PROVISIONAL_DONE", "CERTIFIED_DONE"})
            self.assertTrue(candidate["verifier_requirements"])
            self.assertEqual(self.validate_schema(candidate, "branch_candidate.schema.json"), [])
            self.assertTrue((self.run_dir / candidate["plan_graph_path"]).is_file())
            self.assertTrue((self.run_dir / candidate["artifact_registry_path"]).is_file())
            self.assertTrue((self.run_dir / candidate["task_graph_path"]).is_file())

    def test_generated_branch_set_validates(self):
        self.generate()
        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("BRANCH_SET_VALID", result.stdout)

    def test_branch_claiming_forbidden_final_authority_fails_validation(self):
        self.generate()
        candidate_path = self.run_dir / "branches" / "B.MINIMAL" / "branch_candidate.json"
        candidate = load_json(candidate_path)
        candidate["selection_state"] = "CERTIFIED_DONE"
        write_json(candidate_path, candidate)

        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("claims forbidden final authority", result.stdout)

    def test_missing_verifier_requirements_fail_validation(self):
        self.generate()
        candidate_path = self.run_dir / "branches" / "B.MINIMAL" / "branch_candidate.json"
        candidate = load_json(candidate_path)
        candidate["verifier_requirements"] = []
        write_json(candidate_path, candidate)

        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("missing verifier requirements", result.stdout)

    def test_duplicate_artifact_id_fails_validation(self):
        self.generate()
        registry_path = self.run_dir / "branches" / "B.MINIMAL" / "artifact_registry.json"
        registry = load_json(registry_path)
        registry["artifacts"].append(dict(registry["artifacts"][0]))
        write_json(registry_path, registry)

        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("duplicate artifact_id", result.stdout)

    def test_path_escape_fails_validation(self):
        self.generate()
        registry_path = self.run_dir / "branches" / "B.MINIMAL" / "artifact_registry.json"
        registry = load_json(registry_path)
        registry["artifacts"][0]["path"] = "../escaped.txt"
        write_json(registry_path, registry)

        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("branch path escapes run folder", result.stdout)

    def test_planner_touching_verifier_artifacts_fails_validation(self):
        self.generate()
        registry_path = self.run_dir / "branches" / "B.MINIMAL" / "artifact_registry.json"
        registry = load_json(registry_path)
        registry["artifacts"][0]["path"] = "verifier_artifacts/V.FORGED.json"
        write_json(registry_path, registry)

        result = run_python(str(BRANCH_GENERATOR), str(self.run_dir), "--validate")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("artifact touches verifier_artifacts", result.stdout)


if __name__ == "__main__":
    unittest.main()
