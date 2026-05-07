import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = (
    ROOT
    / ".agentic-pi"
    / "diagnostics"
    / "pi_real_interactive"
    / "prompts"
    / "real_pi_chain_smoke_prompt.txt"
)
TRANSCRIPT_PATH = (
    ROOT
    / ".agentic-pi"
    / "diagnostics"
    / "pi_real_interactive"
    / "transcripts"
    / "real_pi_chain_smoke_result.txt"
)
DOC_PATH = ROOT / "docs" / "V2_3_REAL_PI_INTERACTIVE_SMOKE.md"

ALLOWED_COMMAND = (
    "python .agentic-pi/runtime/run_pi_chain_smoke.py --live --clean "
    "--target-run-id pi_smoke_real_interactive_p2_strong"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PiRealInteractiveSmokeDocTests(unittest.TestCase):
    def test_real_pi_prompt_fixture_locks_single_action_contract(self):
        prompt = read(PROMPT_PATH)

        self.assertIn("You are Mercury inside Pi", prompt)
        self.assertIn("Do not certify DONE yourself", prompt)
        self.assertEqual(prompt.count(ALLOWED_COMMAND), 1)
        self.assertIn(".agentic-runs/pi_chain_smoke_outputs/pi_chain_runtime_result.json", prompt)
        self.assertIn("Final status comes only from certify_run.py and policy_engine.py", prompt)
        self.assertIn("If the file is missing, report MISSING for each field", prompt)

    def test_real_pi_transcript_records_pass_and_certifier_authority(self):
        transcript = read(TRANSCRIPT_PATH)

        self.assertIn("Operator launched the real Pi agent from cmd", transcript)
        self.assertIn("pi", transcript)
        self.assertEqual(transcript.count(ALLOWED_COMMAND), 2)
        self.assertIn("result_status: PASS", transcript)
        self.assertIn('"final_status.md":"CERTIFIED_DONE"', transcript)
        self.assertIn('"certification.json":"CERTIFIED_DONE"', transcript)
        self.assertIn('"policy_decision.json":"CERTIFIED_DONE"', transcript)
        self.assertIn("status_artifacts_agree: true", transcript)
        self.assertIn("final_status_authority: certifier_only", transcript)
        self.assertIn("can_certify_done: false", transcript)
        self.assertIn("not automated CI evidence", transcript)
        self.assertIn("does not prove arbitrary Pi autonomy", transcript)

    def test_v23_doc_locks_real_pi_interactive_boundary(self):
        doc = read(DOC_PATH)

        self.assertIn("REAL PI INTERACTIVE SMOKE EVIDENCE RECORDED", doc)
        self.assertIn("pi = the real external Pi agent launched from cmd", doc)
        self.assertIn("Mercury = the LLM behavior inside Pi", doc)
        self.assertIn(".agentic-pi/runtime/pi_cli.py = repo-local deterministic harness helper, not Pi", doc)
        self.assertIn("local smoke evidence, not automated CI evidence", doc)
        self.assertIn("A real Pi/Mercury interactive smoke can follow", doc)
        self.assertIn("final_status_authority: certifier_only", doc)
        self.assertIn("can_certify_done: false", doc)
        self.assertIn("Full autonomous Pi goal-runner runtime is proven", doc)
        self.assertIn("Mercury can certify DONE", doc)
        self.assertIn("Both unsafe claims remain false", doc)


if __name__ == "__main__":
    unittest.main()
