#!/usr/bin/env python3
"""Run a deterministic seed evaluation for prompt-improver outputs.

This diagnostic runner scores candidate improved prompts against small seed
cases. It does not call an LLM, does not certify DONE, and does not prove broad
prompt coverage. It is meant to stop us from trusting prompts merely because
they sound cleaner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_DIR = ROOT / ".agentic-pi" / "diagnostics" / "prompt_compiler_eval" / "cases"
VALIDATOR_PATH = ROOT / ".agentic-pi" / "validators" / "validate_prompt_eval_case.py"


SECTION_TEMPLATE = """You are improving a prompt for {target_model}.

Original user sentence:
{raw_prompt}

Task type:
{task_type}

Goal:
Preserve the user's intent while making the prompt explicit, testable, and safe.

Constraints:
- Do not invent hidden context.
- Prefer compact, executable instructions over hype words.
- If instructions conflict, state priority rules instead of pretending there is no conflict.
- If information is missing, list missing information and provide a safe default prompt.
- Do not allow self-certified DONE; require concrete evidence before any completion claim.

Output format:
Return an improved prompt with these sections: Goal, Context, Constraints, Output Format, Verification, Failure Handling.

Verification:
The improved prompt must include measurable success criteria, evidence requirements, and concrete failure handling.
"""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_cases(cases_dir: Path) -> list[dict]:
    validator = load_module("validate_prompt_eval_case", VALIDATOR_PATH)
    cases = []
    for path in sorted(cases_dir.glob("*.json")):
        data = load_json(path)
        errors = validator.validate_case(data, source=str(path))
        if errors:
            raise ValueError("Invalid prompt eval case:\n" + "\n".join(errors))
        data["_path"] = str(path)
        cases.append(data)
    if not cases:
        raise ValueError(f"No prompt eval cases found in {cases_dir}")
    return cases


def generate_v0_candidate(case: dict) -> str:
    """Generate a deterministic baseline improved prompt from raw prompt only.

    The seed evaluator intentionally avoids feeding expected_behavior,
    failure_traps, or scoring checks into this candidate. Otherwise the eval
    would only prove that the candidate copied the answer key.
    """
    raw = case["raw_prompt"]
    lower = raw.lower()
    additions: list[str] = []

    if any(term in lower for term in ("done", "looks okay", "finish")):
        additions.append("False DONE guard: do not make a completion claim until tests, logs, changed files, verifier output, or other concrete evidence are available.")
    if any(term in lower for term in ("search", "paper", "latest", "best")):
        additions.append("Research rule: define search scope, recency/date window, source quality, citations, evidence table, comparison criteria, and uncertainty.")
    if any(term in lower for term in ("code", "fix", "bug")):
        additions.append("Coding rule: diagnose first, make the smallest safe minimal patch, do not rewrite unnecessarily, explain changed lines, and run tests or validation checks.")
    if "plan" in lower:
        additions.append("Planning rule: check assumptions, risks, dependencies, missing components, milestones, and failure handling before judging whether the plan is good.")
    if any(term in lower for term in ("honest", "wrong", "do not agree", "keep my sentence", "voice")):
        additions.append("Voice rule: preserve the user's voice and skeptical style; classify claims as Correct, Partially correct, Weak, Wrong, or Not enough evidence.")
    if any(term in lower for term in ("my model", "make this better")):
        additions.append("Missing information rule: list missing information, ask only necessary questions, and provide a safe default without assuming hidden context.")
    if "tool" in lower:
        additions.append("Tool policy: define when tools are allowed, record evidence in a tool log or evidence ledger, stop on repeated tool failure, and report uncertainty.")
    if any(term in lower for term in ("best expert", "never fail", "perfect", "all possible")):
        additions.append("Compression rule: remove hype and impossible claims; produce a compact, realistic prompt with a concrete goal and success criteria.")
    if any(term in lower for term in ("but", "do not ask", "very short")):
        additions.append("Conflict rule: identify contradictions and resolve them with explicit priority rules.")

    if not additions:
        additions.append("General rule: remove vague wording, add constraints, define output format, include verification, and name failure traps.")

    return SECTION_TEMPLATE.format(
        target_model=case["target_model"],
        raw_prompt=raw,
        task_type=case["task_type"],
    ) + "\nHeuristic additions:\n" + "\n".join(f"- {item}" for item in additions) + "\n"


def candidate_path_for(candidate_dir: Path, case_id: str) -> Path | None:
    for suffix in (".md", ".txt", ".prompt", ".json"):
        path = candidate_dir / f"{case_id}{suffix}"
        if path.is_file():
            return path
    return None


def load_candidate(candidate_dir: Path | None, case: dict, *, generate_v0: bool) -> tuple[str, str]:
    if candidate_dir:
        path = candidate_path_for(candidate_dir, case["case_id"])
        if path:
            if path.suffix == ".json":
                data = load_json(path)
                if isinstance(data, dict):
                    for key in ("improved_prompt", "prompt", "candidate", "execution_prompt"):
                        if isinstance(data.get(key), str):
                            return data[key], str(path)
                raise ValueError(f"{path} must contain improved_prompt, prompt, candidate, or execution_prompt string")
            return path.read_text(encoding="utf-8"), str(path)
        if not generate_v0:
            raise ValueError(f"Missing candidate for {case['case_id']} in {candidate_dir}")
    if generate_v0:
        return generate_v0_candidate(case), "generated_v0"
    return case["raw_prompt"], "raw_prompt_baseline"


def check_present(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def score_candidate(case: dict, candidate: str) -> dict:
    results = []
    points = 0
    max_points = 0
    hard_fail_reasons = []

    for check in case["scoring_checks"]:
        check_points = int(check["points"])
        max_points += check_points
        passed = check_present(candidate, check["must_include_any"])
        if passed:
            points += check_points
        elif check.get("hard_fail") is True:
            hard_fail_reasons.append(check["check_id"])
        results.append(
            {
                "check_id": check["check_id"],
                "description": check.get("description", ""),
                "points": check_points if passed else 0,
                "max_points": check_points,
                "passed": passed,
                "hard_fail": bool(check.get("hard_fail", False)),
            }
        )

    score_10 = round((points / max_points) * 10, 2) if max_points else 0.0
    if hard_fail_reasons:
        verdict = "FAIL"
    elif score_10 >= 7.0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "score": score_10,
        "points": points,
        "max_points": max_points,
        "verdict": verdict,
        "hard_fail_reasons": hard_fail_reasons,
        "checks": results,
    }


def run_eval(cases: list[dict], candidate_dir: Path | None, *, generate_v0: bool, write_candidates: Path | None) -> dict:
    case_results = []
    for case in cases:
        candidate, source = load_candidate(candidate_dir, case, generate_v0=generate_v0)
        if write_candidates:
            out_path = write_candidates / f"{case['case_id']}.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(candidate, encoding="utf-8")
        result = score_candidate(case, candidate)
        result["candidate_source"] = source
        case_results.append(result)

    pass_count = sum(1 for row in case_results if row["verdict"] == "PASS")
    average_score = round(sum(row["score"] for row in case_results) / len(case_results), 2)
    return {
        "schema_version": "prompt_compiler_eval_result_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(case_results),
        "pass_count": pass_count,
        "fail_count": len(case_results) - pass_count,
        "average_score": average_score,
        "passing_threshold": 7.0,
        "claim_boundary": "Seed diagnostic only; not proof of arbitrary prompt improvement or broad prompt coverage.",
        "cases": case_results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run prompt compiler seed evaluation.")
    parser.add_argument("--cases-dir", default=str(DEFAULT_CASES_DIR))
    parser.add_argument("--candidate-dir", default="", help="Directory containing <case_id>.md/.txt/.json candidate prompts")
    parser.add_argument("--generate-v0", action="store_true", help="Use deterministic v0 candidates when no candidate file exists")
    parser.add_argument("--write-candidates", default="", help="Optional directory to write generated/loaded candidates")
    parser.add_argument("--output", default="", help="Optional JSON result output path")
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases_dir))
    candidate_dir = Path(args.candidate_dir) if args.candidate_dir else None
    if candidate_dir and not candidate_dir.is_dir():
        raise SystemExit(f"candidate directory not found: {candidate_dir}")
    write_candidates = Path(args.write_candidates) if args.write_candidates else None
    result = run_eval(cases, candidate_dir, generate_v0=args.generate_v0, write_candidates=write_candidates)

    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["fail_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
