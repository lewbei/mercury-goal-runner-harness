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


GATE = load_module("memory_write_gate", ROOT / ".agentic-pi" / "runtime" / "memory_write_gate.py")
DECISION_VALIDATOR = load_module(
    "validate_memory_write_gate",
    ROOT / ".agentic-pi" / "validators" / "validate_memory_write_gate.py",
)


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def valid_card(**overrides):
    card = {
        "schema_version": "mempalace_ace_card_v1",
        "card_id": "anti-overclaim-0001",
        "wing": "anti_overclaim",
        "room": "memory_not_evidence",
        "drawer": "cards",
        "type": "mistake_pattern",
        "content": "Memory can suggest, but cannot become evidence, policy, certification, or final status.",
        "source_run_id": "run_source",
        "source_phase": "POLICY_DECIDING",
        "evidence_refs": ["policy_decision.json", "final_status.json"],
        "helpful_count": 1,
        "harmful_count": 0,
        "last_used_run": "",
        "card_status": "candidate",
        "authority_level": "advisory_only",
        "can_certify_done": False,
        "do_not_use_when": [],
    }
    card.update(overrides)
    return card


class MemoryWriteGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="memory_write_gate_"))
        self.run_dir = self.tmp / "run_0001"
        self.memory_root = self.tmp / "memory_root"
        self.run_dir.mkdir(parents=True)
        write_json(
            self.run_dir / "final_status.json",
            {
                "schema_version": "final_status_v1",
                "run_id": "run_0001",
                "status": "CERTIFIED_DONE",
                "status_source": "certification.json",
                "policy_decision_path": "policy_decision.json",
                "certification_path": "certification.json",
                "generated_at": "2026-05-08T00:00:00+00:00",
                "final_status_authority": "certifier_only",
                "can_certify_done": False,
            },
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_valid_decision(self, decision):
        errors = DECISION_VALIDATOR.validate_memory_write_decision(decision)
        self.assertEqual(errors, [])

    def test_memory_write_gate_rejects_authority_leakage(self):
        decision = GATE.promote_card(
            self.run_dir,
            self.memory_root,
            valid_card(policy_override=True),
        )

        self.assertEqual(decision["decision"], "REJECTED")
        self.assertFalse(decision["promoted"])
        self.assertIn("authority-leak", decision["reason"])
        self.assert_valid_decision(decision)

    def test_memory_write_gate_rejects_no_evidence_ref(self):
        decision = GATE.promote_card(
            self.run_dir,
            self.memory_root,
            valid_card(evidence_refs=[]),
        )

        self.assertEqual(decision["decision"], "REJECTED")
        self.assertIn("evidence_ref", decision["reason"])
        self.assert_valid_decision(decision)

    def test_memory_write_gate_rejects_without_certifier_owned_final_status_json(self):
        (self.run_dir / "final_status.json").unlink()

        decision = GATE.promote_card(self.run_dir, self.memory_root, valid_card())

        self.assertEqual(decision["decision"], "REJECTED")
        self.assertIn("final_status.json", decision["reason"])
        self.assert_valid_decision(decision)

    def test_memory_write_gate_promotes_valid_card_after_final_status_json(self):
        decision = GATE.promote_card(self.run_dir, self.memory_root, valid_card())

        self.assertEqual(decision["decision"], "APPROVED")
        self.assertTrue(decision["promoted"])
        self.assertFalse(decision["can_certify_done"])
        self.assertEqual(decision["final_status_authority"], "certifier_only")
        self.assert_valid_decision(decision)
        target = Path(decision["target_path"])
        self.assertTrue(target.is_file())
        self.assertIn((self.memory_root / "durable").resolve(), target.resolve().parents)


if __name__ == "__main__":
    unittest.main()
