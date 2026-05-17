#!/usr/bin/env python3
"""Record adaptive/autoresearch inputs as planning-only evidence.

This layer intentionally separates nondeterministic discovery from deterministic
gates. It may contain findings from web search, model sampling, or human notes,
but this writer only records a deterministic seed pack unless a future caller
adds run-local findings. Validators and certifiers consume the saved JSON only;
they do not fetch the network and they do not treat research as DONE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = ["final_status.json", "final_status.md", "certification.json", "policy_decision.json"]
MAX_RESEARCH_QUESTIONS = 5
MAX_FINDINGS = 8
MAX_PLANNING_INPUTS = 8


class AdaptiveResearchInputsError(RuntimeError):
    """Raised when adaptive research inputs cannot be recorded safely."""


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_run_dir(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        run_dir = candidate
    elif candidate.parts and candidate.parts[0] == ".agentic-runs":
        run_dir = ROOT / candidate
    else:
        run_dir = RUNS_ROOT / raw
    run_dir = run_dir.resolve()
    runs_root = RUNS_ROOT.resolve()
    if run_dir != runs_root and runs_root not in run_dir.parents:
        raise AdaptiveResearchInputsError(f"run directory must be under .agentic-runs: {raw}")
    if not run_dir.is_dir():
        raise AdaptiveResearchInputsError(f"run directory missing: {raw}")
    return run_dir


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def content_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def truncate(text: str, limit: int = 140) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def source_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    sources = [
        ("goal_contract.json", True),
        ("task_type_decision.json", False),
        ("strategy_candidates.json", True),
        ("strategy_applicability.json", False),
        ("retrieved_experience.json", False),
    ]
    return [
        {"path": rel_path, "required": required, "exists": (run_dir / rel_path).is_file()}
        for rel_path, required in sources
    ]


def build_research_questions(goal: dict, task_type: str) -> list[dict[str, str]]:
    prompt = truncate(goal.get("cleaned_goal") or goal.get("intent") or goal.get("raw_user_prompt") or "the run goal")
    questions = [
        {
            "question_id": "RQ.PLANNING_METHODS",
            "question": f"Which bounded planning/search method lessons apply to this {task_type} goal without changing certifier authority?",
            "rationale": "Adaptive research can widen planning alternatives before deterministic strategy selection is audited.",
            "status": "recorded_seed",
        },
        {
            "question_id": "RQ.VERIFIER_FOLLOWUP",
            "question": f"What verifier evidence would catch a plausible false-DONE for: {prompt}",
            "rationale": "Research findings are useful only if they create concrete verifier follow-up obligations.",
            "status": "recorded_seed",
        },
        {
            "question_id": "RQ.REPRODUCIBILITY",
            "question": "What provenance must be recorded when adaptive LLM or web research is non-deterministic?",
            "rationale": "Deterministic validators need saved inputs, hashes, source URLs, and model/request metadata instead of live claims.",
            "status": "recorded_seed",
        },
    ]
    return questions[:MAX_RESEARCH_QUESTIONS]


def make_finding(
    *,
    finding_id: str,
    source_type: str,
    source_title: str,
    source_url: str,
    claim: str,
    planning_implication: str,
    limitations: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    stable_payload = {
        "finding_id": finding_id,
        "source_title": source_title,
        "source_url": source_url,
        "claim": claim,
        "planning_implication": planning_implication,
        "limitations": limitations,
    }
    return {
        "finding_id": finding_id,
        "source_type": source_type,
        "source_title": source_title,
        "source_url": source_url,
        "claim": claim,
        "planning_implication": planning_implication,
        "limitations": limitations,
        "provenance": {
            "retrieval_method": "deterministic_seed_record",
            "retrieved_by": "adaptive_research_inputs.py",
            "retrieved_at": "recorded_at_runtime",
            "content_hash": content_hash(stable_payload),
            "network_access": False,
            "llm_sampling": False,
        },
        "evidence_refs": evidence_refs,
        "authority_impact": "none",
        "can_certify_done": False,
        "external_source_design_only": True,
        "code_copied": False,
    }


def build_default_findings() -> list[dict[str, Any]]:
    findings = [
        make_finding(
            finding_id="F.TOT.BOUNDED_FRONTIER",
            source_type="paper",
            source_title="Tree of Thoughts: Deliberate Problem Solving with Large Language Models",
            source_url="https://proceedings.neurips.cc/paper/2023/hash/271db9922b8d1f4dd7aaef84ed5ac703-Abstract.html",
            claim="Branching over generated thoughts can improve hard planning, but the search is heuristic and budget-bound.",
            planning_implication="Record generation/evaluation/selection branches and rejected alternatives; never call the frontier exhaustive.",
            limitations="LLM self-evaluation and voting are not independent verifier evidence.",
            evidence_refs=["goal_contract.json", "strategy_candidates.json"],
        ),
        make_finding(
            finding_id="F.GOT.OPERATION_GRAPH",
            source_type="paper",
            source_title="Graph of Thoughts: Solving Elaborate Problems with Large Language Models",
            source_url="https://arxiv.org/abs/2308.09687",
            claim="Graph-structured operations can combine, score, improve, and aggregate reasoning paths.",
            planning_implication="Keep operation dependencies inspectable as planning graph evidence while forbidding graph aggregation from certifying DONE.",
            limitations="Operation scores are planning heuristics unless backed by deterministic verifier artifacts.",
            evidence_refs=["planning_search_tree.json"],
        ),
        make_finding(
            finding_id="F.LATS.EXTERNAL_FEEDBACK",
            source_type="paper",
            source_title="Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models",
            source_url="https://proceedings.mlr.press/v235/zhou24r.html",
            claim="MCTS-style selection, expansion, evaluation, reflection, and external feedback can improve adaptive agent planning.",
            planning_implication="Use external feedback as planning input and risk signal; require independent verifier evidence before policy/certifier handoff.",
            limitations="Rollout rewards, reflections, and environment feedback are not final status authority.",
            evidence_refs=["strategy_candidates.json", "verifier_contract.json"],
        ),
        make_finding(
            finding_id="F.REPRO.SEED_FINGERPRINT",
            source_type="engineering_doc",
            source_title="OpenAI advanced usage: reproducible outputs",
            source_url="https://developers.openai.com/api/docs/guides/advanced-usage#reproducible-outputs",
            claim="LLM calls are non-deterministic by default; seed and system_fingerprint are best-effort reproducibility metadata, not guarantees.",
            planning_implication="When adaptive LLM research is used, save prompts, parameters, seed, model id, system fingerprint, output hash, and source URLs.",
            limitations="Matching seeds and fingerprints reduce variation but do not prove output quality or correctness.",
            evidence_refs=["adaptive_research_inputs.json"],
        ),
        make_finding(
            finding_id="F.EVAL.REPRODUCIBLE_HARNESS",
            source_type="paper",
            source_title="Lessons from the Trenches on Reproducible Evaluation of Language Models",
            source_url="https://arxiv.org/html/2405.14782v1",
            claim="Evaluation results are sensitive to prompts, implementation details, sample choices, and model changes.",
            planning_implication="Prefer deterministic schema/constraint/trace validators first; record adaptive artifacts for audit and replay rather than live fetching.",
            limitations="A saved research finding can guide validation design but does not replace actual validators.",
            evidence_refs=["adaptive_research_inputs.json", "planning_coverage.json"],
        ),
    ]
    return findings[:MAX_FINDINGS]


def build_planning_inputs(findings: list[dict[str, Any]], candidate_ids: list[str]) -> list[dict[str, Any]]:
    finding_ids = [item["finding_id"] for item in findings]
    inputs = [
        {
            "input_id": "AI.SEARCH_FRONTIER_BREADTH",
            "finding_refs": [ref for ref in ["F.TOT.BOUNDED_FRONTIER", "F.GOT.OPERATION_GRAPH", "F.LATS.EXTERNAL_FEEDBACK"] if ref in finding_ids],
            "applies_to": ["planning_search_tree", "planning_coverage"],
            "recommendation": "Expose selected, rejected, blocked, and deferred branches from any adaptive search; keep budgets explicit.",
            "required_verifier_followup": "Verifier artifacts must independently check the selected branch output; branch scores do not prove correctness.",
            "integration_status": "recorded_for_planning",
            "authority_level": "planning_only",
            "can_certify_done": False,
        },
        {
            "input_id": "AI.PROVENANCE_FOR_NONDETERMINISM",
            "finding_refs": [ref for ref in ["F.REPRO.SEED_FINGERPRINT", "F.EVAL.REPRODUCIBLE_HARNESS"] if ref in finding_ids],
            "applies_to": ["verifier_strategy", "replay"],
            "recommendation": "Record exact prompts, queries, model/provider metadata, source URLs, timestamps, and content hashes for any live autoresearch.",
            "required_verifier_followup": "Deterministic validators must validate the saved artifact only and must not depend on fresh network fetches.",
            "integration_status": "recorded_for_planning",
            "authority_level": "planning_only",
            "can_certify_done": False,
        },
        {
            "input_id": "AI.CANDIDATE_RISK_REVIEW",
            "finding_refs": finding_ids[:MAX_FINDINGS],
            "applies_to": ["risk_register", "verification_strategy"],
            "recommendation": "Use adaptive research to add risk notes and verifier follow-up for candidate strategies: " + (", ".join(candidate_ids) or "no candidate ids recorded"),
            "required_verifier_followup": "Policy/certifier must still require verifier_contract.json and verifier_artifacts/*.json before any final status.",
            "integration_status": "recorded_for_planning",
            "authority_level": "planning_only",
            "can_certify_done": False,
        },
    ]
    return inputs[:MAX_PLANNING_INPUTS]


def build_adaptive_research_inputs(run_dir: Path) -> dict[str, Any]:
    goal = load_json(run_dir / "goal_contract.json", {}) or {}
    candidates_doc = load_json(run_dir / "strategy_candidates.json", {}) or {}
    task_type_doc = load_json(run_dir / "task_type_decision.json", {}) or {}

    if not goal:
        raise AdaptiveResearchInputsError("goal_contract.json is required")
    if not candidates_doc:
        raise AdaptiveResearchInputsError("strategy_candidates.json is required")

    task_type = str(task_type_doc.get("task_type") or candidates_doc.get("task_type") or "unknown")
    candidates = [item for item in candidates_doc.get("candidates", []) if isinstance(item, dict)]
    candidate_ids = unique([str(item.get("strategy_id", "")).strip() for item in candidates if item.get("strategy_id")])
    findings = build_default_findings()
    research_questions = build_research_questions(goal, task_type)
    planning_inputs = build_planning_inputs(findings, candidate_ids)

    created_at = utc_now()
    return {
        "schema_version": "adaptive_research_inputs_v1",
        "run_id": run_dir.name,
        "generated_by": "adaptive-research-inputs-v1",
        "generated_at": created_at,
        "authority": {
            "authority_level": "planning_input_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
            "can_write_status_artifacts": False,
            "claim_correctness": False,
            "claim_exhaustive_research": False,
        },
        "determinism_boundary": {
            "adaptive_generation_may_be_nondeterministic": True,
            "deterministic_validation_required": True,
            "validators_must_not_fetch_network": True,
            "certifier_ignores_as_authority": True,
            "replay_uses_recorded_sources_only": True,
        },
        "collection_config": {
            "mode": "deterministic_seed_record",
            "external_network_access_performed": False,
            "llm_sampling_performed": False,
            "max_research_questions": MAX_RESEARCH_QUESTIONS,
            "max_findings": MAX_FINDINGS,
            "max_planning_inputs": MAX_PLANNING_INPUTS,
            "non_exhaustive_research_claim": "bounded_not_exhaustive",
            "future_live_research_requirements": [
                "save exact query or prompt text",
                "save provider/model/version, seed, temperature, and system fingerprint when available",
                "save source URLs and content hashes",
                "save retrieval timestamp and tool name",
                "treat findings as planning inputs only",
            ],
        },
        "implementation_boundary": {
            "source_code_origin": "harness_native_no_vendor_copy",
            "external_sources_are_design_inputs_only": True,
            "external_code_copied": False,
            "external_dependencies_added": False,
        },
        "status_artifact_write_policy": {
            "write_scope": "run_local_planning_artifact_only",
            "forbidden_paths": STATUS_ARTIFACTS,
            "attempted_status_write": False,
        },
        "source_artifacts": source_artifacts(run_dir),
        "research_questions": research_questions,
        "findings": findings,
        "planning_inputs": planning_inputs,
        "integration_contract": {
            "consumed_by": ["planning_search_tree.py", "planning_coverage.py", "full_verify.py"],
            "must_not_be_consumed_by": ["policy_engine.py as final-status authority", "certify_run.py as final-status authority"],
            "required_before_certification": [
                "validate_adaptive_research_inputs.py passes",
                "validate_planning_search_tree.py passes",
                "validate_planning_coverage.py passes",
                "verifier_contract.json exists",
                "verifier_artifacts/*.json exist",
            ],
            "authority_boundary": "Adaptive research can change planning questions, risks, and verifier follow-up; it cannot certify DONE.",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write adaptive_research_inputs.json as planning-only evidence.")
    parser.add_argument("run", help="Run id or .agentic-runs/<run_id> path")
    args = parser.parse_args(argv)
    try:
        run_dir = resolve_run_dir(args.run)
        artifact = build_adaptive_research_inputs(run_dir)
        write_json(run_dir / "adaptive_research_inputs.json", artifact)
    except Exception as exc:
        print(f"ADAPTIVE_RESEARCH_INPUTS_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(artifact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
