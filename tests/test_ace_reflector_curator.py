import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFLECTOR = load_module("ace_reflector", ROOT / ".agentic-pi" / "runtime" / "ace_reflector.py")
CURATOR = load_module("ace_curator", ROOT / ".agentic-pi" / "runtime" / "ace_curator.py")
SCHEMA_VALIDATOR = load_module("validate_schema", ROOT / ".agentic-pi" / "validators" / "validate_schema.py")


def context_card(card_id):
    return {
        "card_id": card_id,
        "wing": "anti_overclaim",
        "room": "memory_not_evidence",
        "reason_selected": "test",
        "content": "Memory can suggest. Policy decides. Certifier writes final status.",
        "evidence_refs": ["policy_decision.json"],
        "authority_level": "advisory_only",
        "can_certify_done": False,
    }


def durable_card(card_id="anti-overclaim-0001"):
    return {
        "schema_version": "mempalace_ace_card_v1",
        "card_id": card_id,
        "wing": "anti_overclaim",
        "room": "memory_not_evidence",
        "drawer": "cards",
        "type": "mistake_pattern",
        "content": "Memory cannot enter evidence_index.json or certify DONE.",
        "source_run_id": "run_0001",
        "source_phase": "VERIFYING",
        "evidence_refs": ["evidence_index.json"],
        "helpful_count": 1,
        "harmful_count": 0,
        "last_used_run": "",
        "card_status": "candidate",
        "authority_level": "advisory_only",
        "can_certify_done": False,
        "do_not_use_when": [],
    }


class AceReflectorCuratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ace_reflector_curator_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def validate_schema(self, obj, schema_name):
        schema = SCHEMA_VALIDATOR.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return SCHEMA_VALIDATOR.validate(obj, schema)

    def test_ace_reflector_marks_helpful_memory(self):
        report = REFLECTOR.build_reflection_report(
            "run_1",
            [context_card("card-a")],
            outcome_status="CERTIFIED_DONE",
        )

        self.assertEqual([row["card_id"] for row in report["helpful_cards"]], ["card-a"])
        self.assertFalse(report["can_write_durable_memory"])
        self.assertFalse(report["can_certify_done"])
        self.assertEqual(self.validate_schema(report, "reflection_report.schema.json"), [])

    def test_ace_reflector_marks_harmful_memory(self):
        report = REFLECTOR.build_reflection_report(
            "run_1",
            [context_card("card-a")],
            outcome_status="NOT_DONE",
        )

        self.assertEqual([row["card_id"] for row in report["harmful_cards"]], ["card-a"])
        self.assertFalse(report["can_write_durable_memory"])
        self.assertEqual(self.validate_schema(report, "reflection_report.schema.json"), [])

    def test_curator_candidate_cannot_directly_write_durable_memory(self):
        delta = CURATOR.build_curator_delta(
            "run_1",
            "source_run_1",
            durable_card(),
            reason="candidate lesson from completed run",
        )
        output = self.tmp / "memory" / "curator_delta_candidates.jsonl"
        CURATOR.write_delta_candidate(output, delta)

        self.assertTrue(output.is_file())
        self.assertFalse(delta["can_write_durable_memory"])
        self.assertFalse((self.tmp / "durable").exists())
        self.assertEqual(self.validate_schema(delta, "curator_delta.schema.json"), [])
        row = json.loads(output.read_text(encoding="utf-8").strip())
        self.assertEqual(row["card"]["card_id"], "anti-overclaim-0001")

    def test_curator_requires_source_run_id(self):
        with self.assertRaises(ValueError):
            CURATOR.build_curator_delta("run_1", "", durable_card())


if __name__ == "__main__":
    unittest.main()
