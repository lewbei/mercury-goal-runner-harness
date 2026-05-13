import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
VALIDATOR = ".agentic-pi/validators/validate_reasoning_gate.py"
PROTECTED_STATUS_ARTIFACTS = ["final_status.json", "final_status.md", "certification.json", "policy_decision.json"]


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def authority():
    return {
        "authority_level": "reasoning_gate_only",
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "claim_correctness": False,
    }


class ReasoningGateTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        for run_id in self.run_ids:
            run_dir = RUN_ROOT / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def make_run(self, suffix: str) -> Path:
        run_id = f"test_reasoning_gate_{self._testMethodName}_{suffix}"
        self.run_ids.append(run_id)
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        return run_dir

    def valid_bundle(self, run_id: str) -> dict[str, dict]:
        frames = []
        for index in range(1, 6):
            frame_id = f"F{index}"
            frames.append(
                {
                    "frame_id": frame_id,
                    "title": f"Frame {index}: distinct approach {index}",
                    "thesis": f"Use approach {index} to test the problem from a distinct angle.",
                    "rationale": f"This frame exists to prevent one-path collapse for angle {index}.",
                    "assumptions": [f"A{index}"],
                    "expected_evidence": [f"Evidence needed for approach {index}."],
                }
            )

        assumptions = [
            {
                "assumption_id": f"A{index}",
                "frame_ids": [f"F{index}"],
                "statement": f"Assumption for frame {index} is explicit.",
                "risk_if_false": f"Frame {index} becomes weak if this is false.",
                "validation_method": "Check with verifier-owned evidence before any completion claim.",
            }
            for index in range(1, 6)
        ]

        attacks = [
            {
                "attack_id": f"AT{index}",
                "target_frame_id": f"F{index}",
                "weakness": f"Attack frame {index} for hidden assumptions and missing evidence.",
                "severity": "medium",
                "resolution": "mitigated" if index == 1 else "accepted_rejection",
                "mitigation_or_rejection": "Selected frame has mitigation." if index == 1 else "Rejected in favor of stronger frame.",
            }
            for index in range(1, 6)
        ]

        return {
            "frame_candidates.json": {
                "schema_version": "frame_candidates_v1",
                "run_id": run_id,
                "generated_by": "test-fixture",
                "authority": authority(),
                "frames": frames,
            },
            "assumption_matrix.json": {
                "schema_version": "assumption_matrix_v1",
                "run_id": run_id,
                "generated_by": "test-fixture",
                "authority": authority(),
                "assumptions": assumptions,
            },
            "attack_report.json": {
                "schema_version": "attack_report_v1",
                "run_id": run_id,
                "generated_by": "test-fixture",
                "authority": authority(),
                "attacks": attacks,
            },
            "selection_decision.json": {
                "schema_version": "selection_decision_v1",
                "run_id": run_id,
                "generated_by": "test-fixture",
                "authority": authority(),
                "decision_status": "FRAME_SELECTED",
                "selected_frame_id": "F1",
                "rejected_frame_ids": ["F2", "F3", "F4", "F5"],
                "rationale": "F1 is selected only after alternatives were attacked and rejected.",
                "evidence_refs": ["frame_candidates.json", "attack_report.json"],
            },
            "reasoning_certification.json": {
                "schema_version": "reasoning_certification_v1",
                "run_id": run_id,
                "generated_by": "test-fixture",
                "authority": authority(),
                "status": "CERTIFIED_REASONED",
                "reason": "Reasoning gate passed; this is not final DONE certification.",
                "checked_artifacts": [
                    "frame_candidates.json",
                    "assumption_matrix.json",
                    "attack_report.json",
                    "selection_decision.json",
                    "reasoning_certification.json",
                ],
            },
        }

    def write_bundle(self, run_dir: Path, bundle: dict[str, dict]) -> None:
        for filename, data in bundle.items():
            write_json(run_dir / filename, data)

    def validate(self, run_dir: Path):
        return run_python(VALIDATOR, str(run_dir))

    def assertFailsWith(self, result, expected_text: str):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(expected_text, result.stdout)

    def test_valid_multi_frame_reasoning_gate_passes_without_final_status(self):
        run_dir = self.make_run("valid")
        self.write_bundle(run_dir, self.valid_bundle(run_dir.name))

        result = self.validate(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK: reasoning gate valid", result.stdout)
        for protected_name in PROTECTED_STATUS_ARTIFACTS:
            self.assertFalse((run_dir / protected_name).exists(), protected_name)

    def test_one_frame_premature_convergence_fails(self):
        run_dir = self.make_run("one_frame")
        bundle = self.valid_bundle(run_dir.name)
        bundle["frame_candidates.json"]["frames"] = bundle["frame_candidates.json"]["frames"][:1]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "minItems 5")

    def test_duplicate_frame_content_fails(self):
        run_dir = self.make_run("duplicate")
        bundle = self.valid_bundle(run_dir.name)
        bundle["frame_candidates.json"]["frames"][1]["title"] = bundle["frame_candidates.json"]["frames"][0]["title"]
        bundle["frame_candidates.json"]["frames"][1]["thesis"] = bundle["frame_candidates.json"]["frames"][0]["thesis"]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "duplicate normalized frame content")

    def test_missing_attack_for_frame_fails(self):
        run_dir = self.make_run("missing_attack")
        bundle = self.valid_bundle(run_dir.name)
        bundle["attack_report.json"]["attacks"] = [
            attack for attack in bundle["attack_report.json"]["attacks"] if attack["target_frame_id"] != "F5"
        ]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "frame F5 has no attack")

    def test_unsupported_selected_frame_fails(self):
        run_dir = self.make_run("unsupported_selected")
        bundle = self.valid_bundle(run_dir.name)
        bundle["selection_decision.json"]["selected_frame_id"] = "F99"
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "unknown frame 'F99'")

    def test_selected_frame_with_unresolved_blocking_attack_fails(self):
        run_dir = self.make_run("blocking")
        bundle = self.valid_bundle(run_dir.name)
        bundle["attack_report.json"]["attacks"][0]["severity"] = "blocking"
        bundle["attack_report.json"]["attacks"][0]["resolution"] = "unresolved"
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "unresolved blocking attack")

    def test_authority_overclaim_fails(self):
        run_dir = self.make_run("authority")
        bundle = self.valid_bundle(run_dir.name)
        bundle["reasoning_certification.json"]["authority"]["can_certify_done"] = True
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "can_certify_done")

    def test_final_done_status_value_fails(self):
        run_dir = self.make_run("final_done")
        bundle = self.valid_bundle(run_dir.name)
        bundle["reasoning_certification.json"]["status"] = "CERTIFIED_DONE"
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "CERTIFIED_DONE")

    def test_protected_status_artifact_in_run_folder_fails(self):
        run_dir = self.make_run("protected")
        self.write_bundle(run_dir, self.valid_bundle(run_dir.name))
        write_json(run_dir / "final_status.json", {"status": "CERTIFIED_DONE"})

        result = self.validate(run_dir)

        self.assertFailsWith(result, "protected status artifact final_status.json")

    def test_run_id_mismatch_fails(self):
        run_dir = self.make_run("run_id_mismatch")
        bundle = self.valid_bundle(run_dir.name)
        bundle["attack_report.json"]["run_id"] = "different_run"
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "must share one run_id")

    def test_incomplete_rejected_frames_fails(self):
        run_dir = self.make_run("incomplete_rejected")
        bundle = self.valid_bundle(run_dir.name)
        bundle["selection_decision.json"]["rejected_frame_ids"] = ["F2", "F3"]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "must equal all non-selected frames")

    def test_unknown_assumption_frame_id_fails(self):
        run_dir = self.make_run("unknown_assumption")
        bundle = self.valid_bundle(run_dir.name)
        bundle["assumption_matrix.json"]["assumptions"][0]["frame_ids"] = ["F99"]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "assumption A1 references unknown frame_id 'F99'")

    def test_protected_evidence_ref_fails(self):
        run_dir = self.make_run("protected_ref")
        bundle = self.valid_bundle(run_dir.name)
        bundle["selection_decision.json"]["evidence_refs"] = ["final_status.json"]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "must not target protected status artifact")

    def test_escaping_evidence_ref_fails(self):
        run_dir = self.make_run("escaping_ref")
        bundle = self.valid_bundle(run_dir.name)
        bundle["selection_decision.json"]["evidence_refs"] = ["..\\final_status.json"]
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "run-relative and non-escaping")

    def test_embedded_final_status_claim_fails(self):
        run_dir = self.make_run("embedded_status")
        bundle = self.valid_bundle(run_dir.name)
        bundle["selection_decision.json"]["rationale"] = "This proves CERTIFIED_DONE without more checks."
        self.write_bundle(run_dir, bundle)

        result = self.validate(run_dir)

        self.assertFailsWith(result, "must not embed final status value 'CERTIFIED_DONE'")

    def test_outside_run_directory_fails(self):
        run_dir = ROOT / ".agentic-pi" / "tmp_reasoning_gate_outside"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        self.addCleanup(lambda: shutil.rmtree(run_dir) if run_dir.exists() else None)
        run_dir.mkdir(parents=True)
        self.write_bundle(run_dir, self.valid_bundle(run_dir.name))

        result = self.validate(run_dir)

        self.assertFailsWith(result, "direct .agentic-runs/<run_id> directory")


if __name__ == "__main__":
    unittest.main()
