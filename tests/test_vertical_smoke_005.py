#!/usr/bin/env python3
"""Vertical slice test for VS.005: Replay hash mismatch blocks certification.

Proves that:
1. A run with consistent replay (REPLAY_MATCH) passes certification
2. A run with tampered evidence (REPLAY_MISMATCH) has certification blocked to NOT_DONE
3. The replay gate in certify_run.py reads replay_report.json and acts on it
"""

import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_KERNEL_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
CERTIFY_PATH = ROOT / ".agentic-pi" / "validators" / "certify_run.py"
REPLAY_PATH = ROOT / ".agentic-pi" / "replay" / "replay_certification.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_certify(run_dir: Path):
    """Run certify_run.py as a subprocess."""
    return subprocess.run(
        [sys.executable, str(CERTIFY_PATH), str(run_dir)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def sha256_file(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            d.update(chunk)
    return d.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def make_file(path: Path, content: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestVerticalSlice005_ReplayMismatch(unittest.TestCase):
    """VS.005: Replay hash mismatch blocks certification."""

    def setUp(self):
        self.rk = load_module("run_kernel", RUN_KERNEL_PATH)
        self.rc = load_module("replay_certification", REPLAY_PATH)
        self.run_id = "vs005_replay"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def _create_minimal_certifiable_run(self):
        """Create a run with enough evidence to trigger the replay gate."""
        self.rk.create_run(self.run_id)

        # Core files needed by certifier
        make_file(self.run_dir / "goal_contract.json", json.dumps({
            "run_id": self.run_id, "goal": "replay test",
            "final_outputs": ["output.txt"], "done_criteria": ["output.txt exists"],
        }))
        make_file(self.run_dir / "trace.jsonl", '{"event": "start", "timestamp": "2026-01-01T00:00:00Z"}\n')
        make_file(self.run_dir / "step_logs/001.json", json.dumps({
            "run_id": self.run_id, "step_id": 1, "status": "PASSED",
            "action_taken": "test", "files_touched": ["output.txt"],
            "commands_run": ["echo test"], "evidence": ["output.txt created"],
            "pass_condition_satisfied": True, "remaining_work": [],
        }))
        make_file(self.run_dir / "output.txt", "test output")

        # Certification, policy, and final status
        make_file(self.run_dir / "certification.json", json.dumps({"status": "DONE_PASS"}))
        make_file(self.run_dir / "policy_decision.json", json.dumps({"status": "DONE_PASS"}))
        make_file(self.run_dir / "final_status.json", json.dumps({
            "status": "DONE_PASS", "final_status_authority": "certifier_only",
        }))

    # ── Test 1: Replay MATCH allows certification ─────────────────────────

    def test_replay_match_allows_certification(self):
        """When replay says MATCH, certifier should proceed normally."""
        self._create_minimal_certifiable_run()

        # Freeze evidence and run replay
        hashes = self.rc.compute_evidence_hashes(self.run_dir)
        make_file(self.run_dir / "evidence_freeze.json", json.dumps({"artifact_hashes": hashes}))
        self.rc.run_replay_certification(self.run_dir)

        # Verify replay says MATCH
        replay = load_json(self.run_dir / "replay_report.json")
        self.assertEqual(replay["verdict"], "REPLAY_MATCH",
                        "Replay must be MATCH before tampering")

        # Certify
        result = run_certify(self.run_dir)
        cert = load_json(self.run_dir / "certification.json")

        # Replay MATCH should NOT cause NOT_DONE
        replay_failures = [c for c in cert["failed_checks"] if "replay" in c.lower()]
        self.assertEqual(len(replay_failures), 0,
                        f"Replay MATCH should not cause failures: {replay_failures}")
        self.assertIn(cert["status"], ["DONE_PASS", "DONE_FAIL"],
                     "Replay MATCH should not force NOT_DONE")

    # ── Test 2: Replay MISMATCH blocks certification ──────────────────────

    def test_replay_mismatch_blocks_certification(self):
        """When replay says MISMATCH, certifier must return NOT_DONE."""
        self._create_minimal_certifiable_run()

        # Freeze evidence
        hashes = self.rc.compute_evidence_hashes(self.run_dir)
        make_file(self.run_dir / "evidence_freeze.json", json.dumps({"artifact_hashes": hashes}))

        # Run replay (initially should be MATCH)
        self.rc.run_replay_certification(self.run_dir)

        # Tamper with evidence AFTER freeze
        make_file(self.run_dir / "goal_contract.json", json.dumps({
            "run_id": self.run_id, "goal": "TAMPERED GOAL — should be detected",
        }))

        # Re-run replay (should be MISMATCH)
        self.rc.run_replay_certification(self.run_dir)
        replay = load_json(self.run_dir / "replay_report.json")
        self.assertEqual(replay["verdict"], "REPLAY_MISMATCH",
                        "Tampered evidence must cause REPLAY_MISMATCH")

        # Certify
        result = run_certify(self.run_dir)
        cert = load_json(self.run_dir / "certification.json")
        self.assertEqual(cert["status"], "NOT_DONE",
                        "Replay MISMATCH must force NOT_DONE")

        # The failed check must mention replay
        replay_failures = [c for c in cert["failed_checks"] if "replay" in c.lower()]
        self.assertGreater(len(replay_failures), 0,
                          "Replay MISMATCH must appear in failed_checks")

        # final_status.json must also say NOT_DONE
        final = load_json(self.run_dir / "final_status.json")
        self.assertEqual(final["status"], "NOT_DONE")

    # ── Test 3: No replay_report.json = no gate ───────────────────────────

    def test_no_replay_report_no_block(self):
        """Without replay_report.json, the replay gate passes through."""
        self._create_minimal_certifiable_run()

        # No evidence_freeze.json, no replay_report.json
        result = run_certify(self.run_dir)
        cert = load_json(self.run_dir / "certification.json")

        # Should fail normally (missing trace/step evidence), not due to replay
        replay_failures = [c for c in cert["failed_checks"] if "replay" in c.lower()]
        self.assertEqual(len(replay_failures), 0,
                        "Without replay_report, no replay gate failures")


if __name__ == "__main__":
    unittest.main()
