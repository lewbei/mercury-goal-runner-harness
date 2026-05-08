import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class UbiquitousLanguageContractTests(unittest.TestCase):
    def test_harness_terms_schema_defines_canonical_graph_terms(self):
        schema_path = ROOT / ".agentic-pi" / "schemas" / "harness_terms.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        terms_schema = schema["properties"]["terms"]
        terms = terms_schema["items"]["enum"]

        for required in [
            "Goal",
            "Goal Contract",
            "Plan Candidate",
            "Selected Plan",
            "Certification",
            "Pi Report",
            "Monitor Verdict",
        ]:
            self.assertIn(required, terms)
        self.assertEqual(len(terms), len(set(terms)))

    def test_ubiquitous_language_doc_preserves_critical_distinctions(self):
        doc = (ROOT / "docs" / "UBIQUITOUS_LANGUAGE.md").read_text(encoding="utf-8")
        for phrase in [
            "MONITOR_PASS != TASK_DONE",
            "ARTIFACT_EXISTS != GOAL_SATISFIED",
            "SELECTED_PLAN != CORRECT_PLAN",
            "VERIFIER_EXISTS != CERTIFYING_VERIFIER",
            "PI_REPORT != CERTIFICATION",
        ]:
            self.assertIn(phrase, doc)
        self.assertIn("This is not a ban on normal repo language", doc)
        self.assertNotIn("All other terms are prohibited", doc)


if __name__ == "__main__":
    unittest.main()
