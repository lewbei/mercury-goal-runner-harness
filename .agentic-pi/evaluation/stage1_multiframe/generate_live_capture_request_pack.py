#!/usr/bin/env python3
"""Generate the Stage 1 live A/B capture request pack.

This generator creates external capture tasks only. It does not call live models,
does not include model outputs, and does not certify DONE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
DEFAULT_OUTPUT = DEFAULT_DIR / "live_capture_request_pack_v2.json"
MODES = ("normal_prompt", "multiframe_harness")
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
EXPECTED_CAPTURE_FIELDS = [
    "prompt_id",
    "mode",
    "provider",
    "model",
    "model_version",
    "prompt_text",
    "prompt_hash",
    "system_prompt_hash",
    "output_text",
    "output_hash",
    "captured_at",
    "capture_method",
    "provenance",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def capture_instruction(prompt_text: str, mode: str) -> str:
    if mode == "normal_prompt":
        return (
            "Treat the text between <benchmark_prompt> tags as the user question. "
            "Answer that question directly in normal prompting mode. "
            "Do not restate these instructions. Do not use an explicit multi-frame scaffold unless you would naturally do so.\n\n"
            f"<benchmark_prompt>\n{prompt_text}\n</benchmark_prompt>"
        )
    if mode == "multiframe_harness":
        return (
            "Treat the text between <benchmark_prompt> tags as the user question. "
            "Answer that question using the grounded multi-frame harness. Do not restate these instructions.\n\n"
            "Required structure:\n"
            "1. Known facts from the prompt only.\n"
            "2. Assumptions, each labeled prompt-supported or speculative.\n"
            "3. Unknowns / unavailable evidence.\n"
            "4. Claims needing evidence before they can be trusted.\n"
            "5. Distinct frames with attacks on weak paths.\n"
            "6. Rejected bad frames, especially frames that rely on unstated facts.\n"
            "7. Final direction that separates supported conclusions from unknowns.\n\n"
            "Do not invent repo state, tool access, citations, benchmark results, product claims, hidden context, "
            "CI status, dependencies, or live checks. Do not claim completion authority.\n\n"
            f"<benchmark_prompt>\n{prompt_text}\n</benchmark_prompt>"
        )
    raise ValueError(f"unknown mode: {mode}")


def build_request_pack(prompt_set: dict[str, Any], *, request_pack_id: str) -> dict[str, Any]:
    prompts = prompt_set["prompts"]
    tasks = []
    for prompt in prompts:
        for mode in MODES:
            prompt_text = prompt["prompt"]
            tasks.append(
                {
                    "task_id": f"{prompt['prompt_id']}::{mode}",
                    "prompt_id": prompt["prompt_id"],
                    "mode": mode,
                    "prompt_text": prompt_text,
                    "prompt_hash": sha256_text(prompt_text),
                    "capture_instruction": capture_instruction(prompt_text, mode),
                    "expected_capture_fields": list(EXPECTED_CAPTURE_FIELDS),
                    "forbidden_actions": [
                        "Do not fabricate model output.",
                        "Do not omit failed attempts from provenance.",
                        "Do not claim final authority or task completion status.",
                        "Do not include secrets or API keys.",
                        "Do not write protected status artifacts.",
                    ],
                }
            )
    return {
        "schema_version": "stage1_capture_request_pack_v1",
        "request_pack_id": request_pack_id,
        "prompt_set_id": prompt_set["benchmark_id"],
        "authority": {
            "authority_level": "evaluation_request_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        },
        "capture_policy": {
            "requires_external_capture": True,
            "does_not_call_live_models": True,
            "does_not_include_model_outputs": True,
            "required_task_count": len(prompts) * len(MODES),
            "modes": list(MODES),
        },
        "tasks": tasks,
        "claim_boundary": "This request pack is a capture to-do list only. It is not model output, live evidence, scoring evidence, or final certification.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Stage 1 live A/B capture request pack")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "prompt_set.json"))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--request-pack-id", default="stage1_live_capture_request_pack_50x2_v2")
    args = parser.parse_args(argv)

    prompt_set = load_json(Path(args.prompt_set))
    pack = build_request_pack(prompt_set, request_pack_id=args.request_pack_id)
    write_json(Path(args.output), pack)
    print(f"OK: wrote Stage 1 live capture request pack to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
