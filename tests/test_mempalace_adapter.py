import importlib.util
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


ADAPTER = load_module("mempalace_adapter", ROOT / ".agentic-pi" / "runtime" / "mempalace_adapter.py")
VALIDATOR = load_module("validate_memory_card", ROOT / ".agentic-pi" / "validators" / "validate_memory_card.py")


def valid_card(**overrides):
    card = {
        "schema_version": "mempalace_ace_card_v1",
        "card_id": "anti-overclaim-0001",
        "wing": "anti_overclaim",
        "room": "artifact_exists_not_done",
        "drawer": "certification_failures",
        "type": "mistake_pattern",
        "content": "Artifact existence is not task completion; require producer-linked evidence and policy pass.",
        "source_run_id": "run_0001",
        "source_phase": "POLICY_DECIDING",
        "evidence_refs": ["policy_decision.json", "evidence_index.json"],
        "helpful_count": 2,
        "harmful_count": 0,
        "last_used_run": "",
        "card_status": "durable",
        "authority_level": "advisory_only",
        "can_certify_done": False,
        "do_not_use_when": ["external human judgment is required"],
    }
    card.update(overrides)
    return card


class MemPalaceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mempalace_adapter_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_memory_card_requires_evidence_refs(self):
        card = valid_card(evidence_refs=[])

        errors = VALIDATOR.validate_memory_card(card)

        self.assertTrue(errors)
        self.assertTrue(any("evidence_ref" in error for error in errors))

    def test_memory_card_rejects_certification_authority(self):
        card = valid_card(can_certify_done=True, authority_level="certifier")

        errors = VALIDATOR.validate_memory_card(card)

        self.assertTrue(any("cannot certify DONE" in error for error in errors))
        self.assertTrue(any("advisory_only" in error for error in errors))

    def test_adapter_writes_durable_card_under_memory_root(self):
        path = ADAPTER.write_durable_card(self.tmp, valid_card())

        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "certification_failures.jsonl")
        self.assertIn((self.tmp / "durable").resolve(), path.resolve().parents)
        rows = ADAPTER.load_jsonl(path)
        self.assertEqual(rows[0]["authority_level"], "advisory_only")
        self.assertFalse(rows[0]["can_certify_done"])

    def test_adapter_rejects_path_escape_segments(self):
        with self.assertRaises(ValueError):
            ADAPTER.write_durable_card(self.tmp, valid_card(drawer="../escape"))

    def test_durable_layout_creates_expected_wings(self):
        ADAPTER.ensure_durable_layout(self.tmp)

        for wing in ADAPTER.DEFAULT_WING_ROOMS:
            self.assertTrue((self.tmp / "durable" / wing).is_dir())
        self.assertTrue((self.tmp / "index").is_dir())
        self.assertTrue((self.tmp / "verbatim" / "run_excerpts").is_dir())


if __name__ == "__main__":
    unittest.main()
