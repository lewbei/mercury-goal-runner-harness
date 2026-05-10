import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("context_pack_builder", ROOT / ".agentic-pi" / "runtime" / "context_pack_builder.py")
VALIDATOR = load_module("validate_context_pack", ROOT / ".agentic-pi" / "validators" / "validate_context_pack.py")


def card(card_id, **overrides):
    value = {
        "schema_version": "mempalace_ace_card_v1",
        "card_id": card_id,
        "wing": "anti_overclaim",
        "room": "memory_not_evidence",
        "drawer": "cards",
        "type": "mistake_pattern",
        "content": f"{card_id}: memory can suggest, but policy decides and certifier writes final status.",
        "source_run_id": "run_0001",
        "source_phase": "PLANNING",
        "evidence_refs": ["policy_decision.json"],
        "helpful_count": 1,
        "harmful_count": 0,
        "last_used_run": "",
        "card_status": "durable",
        "authority_level": "advisory_only",
        "can_certify_done": False,
        "do_not_use_when": [],
    }
    value.update(overrides)
    return value


class ContextPackBuilderTests(unittest.TestCase):
    def test_context_pack_respects_max_cards(self):
        cards = [card(f"card-{i}", helpful_count=i) for i in range(10)]

        pack = BUILDER.build_context_pack("run_1", "BRANCHING", "select evidence strategy", cards, max_cards=3)

        self.assertEqual(len(pack["cards"]), 3)
        self.assertEqual(VALIDATOR.validate_context_pack(pack), [])

    def test_context_pack_excludes_deprecated_card(self):
        cards = [card("good"), card("deprecated", card_status="deprecated")]

        pack = BUILDER.build_context_pack("run_1", "BRANCHING", "select evidence strategy", cards)

        self.assertEqual([row["card_id"] for row in pack["cards"]], ["good"])
        self.assertEqual(VALIDATOR.validate_context_pack(pack), [])

    def test_context_pack_excludes_harmful_card(self):
        cards = [card("good"), card("bad", helpful_count=0, harmful_count=2)]

        pack = BUILDER.build_context_pack("run_1", "BRANCHING", "select evidence strategy", cards)

        self.assertEqual([row["card_id"] for row in pack["cards"]], ["good"])
        self.assertEqual(VALIDATOR.validate_context_pack(pack), [])

    def test_context_pack_excludes_authority_leakage(self):
        cards = [card("good"), card("bad", can_certify_done=True)]

        pack = BUILDER.build_context_pack("run_1", "BRANCHING", "select evidence strategy", cards)

        self.assertEqual([row["card_id"] for row in pack["cards"]], ["good"])
        self.assertFalse(pack["can_certify_done"])
        self.assertEqual(pack["final_status_authority"], "certifier_only")


if __name__ == "__main__":
    unittest.main()
