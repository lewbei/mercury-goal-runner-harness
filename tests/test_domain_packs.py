import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
PACK_DIR = ROOT / ".agentic-pi" / "domain_packs"
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
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def goal_contract(run_id: str, raw_goal: str, final_output: str = "artifacts/output.txt") -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": raw_goal,
        "intent": raw_goal,
        "cleaned_goal": raw_goal,
        "final_outputs": [final_output],
        "explicit_constraints": ["Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic domain pack selection."],
        "forbidden_actions": ["Do not certify DONE in domain pack artifacts."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": "SIMPLE",
        "done_criteria": [f"{final_output} exists."],
        "failure_criteria": [f"{final_output} missing."],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": raw_goal,
    }


class DomainPackTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def make_run(self, suffix: str, raw_goal: str, final_output: str = "artifacts/output.txt") -> Path:
        run_id = f"test_domain_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        write_json(run_dir / "goal_contract.json", goal_contract(run_id, raw_goal, final_output))
        (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
        return run_dir

    def assert_schema_valid(self, schema_name: str, instance: dict):
        validator = load_schema_validator()
        schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        errors = validator.validate(instance, schema)
        self.assertEqual(errors, [])

    def route_and_select(self, run_dir: Path) -> dict:
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/domain_pack_selector.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)
        selection = load_json(run_dir / "domain_pack_selection.json")
        self.assert_schema_valid("domain_pack_selection.schema.json", selection)
        return selection

    def test_all_domain_packs_are_schema_valid_and_cannot_certify_done(self):
        expected = {"coding", "research", "writing", "debugging", "experiment", "benchmark", "devops"}
        found = {path.stem for path in PACK_DIR.glob("*.json")}
        self.assertEqual(found, expected)

        for path in PACK_DIR.glob("*.json"):
            with self.subTest(path=path.name):
                pack = load_json(path)
                self.assert_schema_valid("domain_pack.schema.json", pack)
                self.assertEqual(pack["final_status_authority"], "certifier_only")
                self.assertFalse(pack["can_certify_done"])
                forbidden = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}
                flat_text = json.dumps(pack)
                self.assertFalse(any(status in flat_text for status in forbidden))

    def test_task_type_selects_expected_domain_pack(self):
        cases = [
            ("coding", "Create a Python CLI script for CSV summary", "tool.py", "coding"),
            ("research", "Write a literature claim audit with source citations", "artifacts/report.md", "research"),
            ("writing", "Write README.md documentation for the harness", "README.md", "writing"),
            ("benchmark", "Create diagnostic benchmark metrics and false pass report", "artifacts/report.md", "benchmark"),
            ("debugging", "Fix the failing traceback in the CLI", "artifacts/patch.md", "debugging"),
            ("experiment", "Run an ablation experiment protocol summary", "artifacts/report.md", "experiment"),
            ("devops", "Draft a docker deployment rollback plan", "artifacts/deploy.md", "devops"),
        ]
        for suffix, raw_goal, final_output, expected_pack in cases:
            with self.subTest(expected_pack=expected_pack):
                run_dir = self.make_run(suffix, raw_goal, final_output)
                selection = self.route_and_select(run_dir)
                self.assertEqual(selection["selection_status"], "SELECTED")
                self.assertEqual(selection["selected_domain_pack"], expected_pack)
                self.assertFalse(selection["can_certify_done"])

    def test_unknown_goal_does_not_guess_unsafe_pack(self):
        run_dir = self.make_run("unknown", "blue sky purpose with no operational keyword")

        selection = self.route_and_select(run_dir)

        self.assertEqual(selection["selection_status"], "NEED_USER_DOMAIN")
        self.assertEqual(selection["selected_domain_pack"], "")
        self.assertEqual(selection["domain_pack_path"], "")
        self.assertFalse(selection["can_certify_done"])
        for status_name in STATUS_FILES:
            self.assertFalse((run_dir / status_name).exists(), status_name)

    def test_domain_pack_enriches_strategy_candidates_without_changing_schema(self):
        run_dir = self.make_run("coding_enriched", "Create a Python CLI script for CSV summary", "tool.py")
        for tool in [
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/domain_pack_selector.py",
            ".agentic-pi/runtime/strategy_generator.py",
        ]:
            result = run_python(tool, str(run_dir))
            self.assertEqual(result.returncode, 0, result.stdout)

        candidates = load_json(run_dir / "strategy_candidates.json")
        self.assertEqual(candidates["domain_pack_applied"], "coding")
        self.assertEqual(candidates["domain_pack_selection_status"], "SELECTED")
        self.assertEqual(len(candidates["candidates"]), 1)
        candidate = candidates["candidates"][0]
        self.assertEqual(candidate["strategy_id"], "S.CODE_ARTIFACT_TEST")
        self.assertIn("P2/P3 behavior verifier required for certification", candidate["verifier_requirements"])
        self.assertIn("placeholder code", candidate["risk_notes"])
        self.assertIn("policy_engine", candidate["required_capabilities"])
        self.assert_schema_valid("strategy_candidate.schema.json", candidate)

    def test_domain_pack_selection_is_wired_into_strategy_proof(self):
        run_id = f"pi_smoke_domain_{self._testMethodName}"
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

        selection = load_json(run_dir / "domain_pack_selection.json")
        candidates = load_json(run_dir / "strategy_candidates.json")
        self.assertEqual(selection["selected_domain_pack"], "writing")
        self.assertEqual(candidates["domain_pack_applied"], "writing")
        self.assertEqual(load_json(run_dir / "certification.json")["status"], "CERTIFIED_DONE")
        self.assertEqual(load_json(run_dir / "strategy_proof.json")["final_status_source"], "certification.json")

    def test_domain_pack_doc_locks_boundary(self):
        doc = (ROOT / "docs" / "V1_8_DOMAIN_PACKS.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("DOMAIN PACKS IMPLEMENTED", doc)
        self.assertIn("domain packs can suggest", doc)
        self.assertIn("domain packs cannot certify DONE", doc)
        self.assertIn("unknown goals do not guess unsafe packs", doc)
        self.assertIn("v1.8 Domain Packs", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)


if __name__ == "__main__":
    unittest.main()
