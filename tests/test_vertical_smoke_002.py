#!/usr/bin/env python3
"""Vertical slice test for VS.002: Work packet dispatches to real agent and reaches ACCEPTED.

Proves the full work packet lifecycle across the kernel:
1. Kernel creates packet (PENDING)
2. Kernel dispatches (DISPATCHED) — agent receives the packet
3. Agent writes result → kernel receives it (RESULT_RECEIVED)
4. Kernel validates (VALIDATING)
5. Kernel accepts (ACCEPTED)
6. Dispatch log records every step
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_KERNEL_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_python(*args):
    """Run a python script as subprocess in repo root, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


class TestVerticalSlice002_WorkPacketLifecycle(unittest.TestCase):
    """VS.002: Full work packet lifecycle — created → dispatched → result → accepted."""

    def setUp(self):
        self.rk = load_module("run_kernel", RUN_KERNEL_PATH)
        self.run_id = "vs002_packet_lifecycle"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id

        # Clean up previous run
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    # ── Test 1: Full lifecycle via kernel API ─────────────────────────────

    def test_full_lifecycle_via_kernel_api(self):
        """Packet progresses PENDING → DISPATCHED → RESULT_RECEIVED → VALIDATING → ACCEPTED."""
        # 1. Create run
        self.rk.create_run(self.run_id)

        # 2. Create packet
        pid = self.rk.create_work_packet(
            self.run_id,
            phase="IMPLEMENTING",
            role="Engineer",
            task="Create a test artifact",
            allowed_write_paths=["artifacts/"],
            max_model_calls=1,
            max_repair_attempts=0,
        )
        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "PENDING")
        self.assertEqual(pkt["phase"], "IMPLEMENTING")

        # 3. Dispatch (simulates supervisor handing packet to agent)
        self.rk.dispatch_packet(self.run_id, pid)
        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "DISPATCHED")
        self.assertIsNotNone(pkt["dispatch_timestamp"])

        # 4. Agent writes result → receive it
        # (In real harness, the agent writes work_results/<packet_id>.json)
        result_content = json.dumps({"artifact_id": "A.TEST", "path": "artifacts/test.txt", "content": "done"})
        result_path = f"work_results/{pid}.json"
        (self.run_dir / result_path).write_text(result_content, encoding="utf-8")
        self.rk.receive_result(self.run_id, pid, result_path)
        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "RESULT_RECEIVED")
        self.assertEqual(pkt["result_path"], result_path)

        # 5. Start validation
        self.rk.start_validation(self.run_id, pid)
        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "VALIDATING")

        # 6. Accept
        val_result = json.dumps({"verdict": "PASS", "checks": ["file_exists"]})
        val_path = f"validation_results/{pid}.json"
        (self.run_dir / val_path).write_text(val_result, encoding="utf-8")
        self.rk.accept_packet(self.run_id, pid, validation_result_path=val_path)
        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "ACCEPTED")
        self.assertEqual(pkt["validation_result_path"], val_path)

    # ── Test 2: Dispatch log records all events ──────────────────────────

    def test_dispatch_log_records_full_lifecycle(self):
        """dispatch_log.jsonl has entries for every stage of the lifecycle."""
        self.rk.create_run(self.run_id)

        pid = self.rk.create_work_packet(
            self.run_id, phase="IMPLEMENTING", role="Engineer",
            task="Log lifecycle test",
        )
        self.rk.dispatch_packet(self.run_id, pid)

        result_content = json.dumps({"status": "done"})
        result_path = f"work_results/{pid}.json"
        (self.run_dir / result_path).write_text(result_content, encoding="utf-8")
        self.rk.receive_result(self.run_id, pid, result_path)
        self.rk.start_validation(self.run_id, pid)

        val_path = f"validation_results/{pid}.json"
        (self.run_dir / val_path).write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
        self.rk.accept_packet(self.run_id, pid, validation_result_path=val_path)

        log = self.rk.get_dispatch_log(self.run_id)
        events = [e["event"] for e in log]

        self.assertIn("run_created", events)
        self.assertIn("work_packet_created", events)
        self.assertIn("work_packet_dispatched", events)
        self.assertIn("work_packet_result_received", events)
        self.assertIn("work_packet_accepted", events)

        # Verify packet id consistency across events
        packet_events = [e for e in log if "work_packet_id" in e]
        for pe in packet_events:
            self.assertEqual(pe["work_packet_id"], pid)

    # ── Test 3: Reject + repair budget enforced ──────────────────────────

    def test_reject_and_repair_budget(self):
        """Rejected packet with zero repair budget stays REJECTED."""
        self.rk.create_run(self.run_id)

        pid = self.rk.create_work_packet(
            self.run_id, phase="IMPLEMENTING", role="Engineer",
            task="Fail once", max_repair_attempts=0,
        )
        self.rk.dispatch_packet(self.run_id, pid)

        result_content = json.dumps({"status": "bad result"})
        (self.run_dir / f"work_results/{pid}.json").write_text(result_content, encoding="utf-8")
        self.rk.receive_result(self.run_id, pid, f"work_results/{pid}.json")
        self.rk.start_validation(self.run_id, pid)
        self.rk.reject_packet(self.run_id, pid, error="Validation failed")

        pkt = self.rk.get_packet(self.run_id, pid)
        self.assertEqual(pkt["status"], "REJECTED")
        self.assertEqual(pkt["error"], "Validation failed")

    # ── Test 4: Packet persistence ───────────────────────────────────────

    def test_packet_persists_to_disk(self):
        """Work packet is written as JSON to work_packets/ and survives reload."""
        self.rk.create_run(self.run_id)
        pid = self.rk.create_work_packet(
            self.run_id, phase="INTAKE", role="Questioner",
            task="Persist test",
        )

        # Verify file on disk
        packet_file = self.run_dir / "work_packets" / f"{pid}.json"
        self.assertTrue(packet_file.exists())
        data = json.loads(packet_file.read_text(encoding="utf-8"))
        self.assertEqual(data["work_packet_id"], pid)
        self.assertEqual(data["status"], "PENDING")

    # ── Test 5: Phase queue tracks packet IDs ────────────────────────────

    def test_phase_queue_tracks_packets(self):
        """Phase queue entry lists the work packet ID."""
        self.rk.create_run(self.run_id)
        pid = self.rk.create_work_packet(
            self.run_id, phase="IMPLEMENTING", role="Engineer",
            task="Queue tracking test",
        )

        pq = self.rk.get_phase_queue(self.run_id)
        impl_phase = [p for p in pq["phases"] if p["phase"] == "IMPLEMENTING"][0]
        self.assertIn(pid, impl_phase["work_packet_ids"])


if __name__ == "__main__":
    unittest.main()
