#!/usr/bin/env python3
"""Progressive skill dispatcher.

Skills are loaded cumulatively as the run advances through phases.
Earlier skills remain in context for later phases. Deterministic phases
(POLICY_DECIDING, REPLAYING, CERTIFYING) inject no agent skills.

Accumulation rule:
  Each phase adds its skill(s) to a growing context.
  No skill is ever removed.
  The agent entering phase N receives all skills for phases 1..N.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


_RUNTIME_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _RUNTIME_DIR.parents[1]


def _default_skills_dir() -> Path:
    for candidate in (
        _ROOT_DIR / ".pi" / "skills",
        _ROOT_DIR / "skills",
        _RUNTIME_DIR.parent / "skills",
    ):
        if candidate.is_dir():
            return candidate
    return _RUNTIME_DIR.parent / "skills"


_SKILLS_DIR = _default_skills_dir()
_PHASE_REGISTRY_PATH = _RUNTIME_DIR.parent / "run_kernel" / "phase_registry.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  Phase → Skill mapping (defined here; could live in a registry file)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE_SKILL_MAP: dict[str, list[str]] = {
    "NEW":                      [],
    "INTAKE":                   ["question-contract"],
    "QUESTIONING":              [],           # same skill carries through
    "RESEARCHING":              ["research-pack"],
    "DESIGNING":                ["design-options"],
    "STRUCTURING":              ["structure-outline"],
    "PLANNING":                 ["root-plan"],
    "WORKTREE_READY":           ["artifact-contract"],
    "IMPLEMENTING":             ["path-grounding"],
    "VALIDATOR_BUILDING":       ["validator-factory"],
    "VALIDATING":               ["harness-grill", "harness-tdd", "harness-diagnose"],
    "EVIDENCE_INDEXING":        [],
    "POLICY_DECIDING":          [],           # deterministic — no agent
    "REPLAYING":                [],           # deterministic — no agent
    "CERTIFYING":               ["harness-certify"],
    "REPORTING":                [],
    "MEMORY_CONSOLIDATING":     ["write-memory"],
    "DONE":                     [],
    "BLOCKED_BY_GOAL_AMBIGUITY":      [],
    "BLOCKED_BY_MISSING_SUCCESS_CRITERIA": [],
    "BLOCKED_BY_VERIFIER_MISSING":     [],
    "BLOCKED_BY_ARTIFACT_MISPLACEMENT": [],
    "BLOCKED_BY_VALIDATOR_UNTRUSTED":  [],
    "BLOCKED_BY_EVIDENCE_GAP":         [],
    "BLOCKED_BY_REPLAY_MISMATCH":      [],
    "BLOCKED_BY_AUTHORITY_VIOLATION":  [],
    "BLOCKED_BY_CHECK_FAILURE":         [],
    "REPAIRING_PLAN":                   ["harness-repair"],
    "REPAIRING_ARTIFACT_ROUTING":       ["harness-repair"],
    "REPAIRING_VALIDATOR":              ["harness-repair"],
    "REPAIRING_EVIDENCE":               ["harness-repair"],
    "REPAIRING_IMPLEMENTATION":         ["harness-repair"],
}

# Phase order for progressive accumulation
PHASE_ORDER = [
    "NEW", "INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING",
    "STRUCTURING", "PLANNING", "WORKTREE_READY", "IMPLEMENTING",
    "VALIDATOR_BUILDING", "VALIDATING", "EVIDENCE_INDEXING",
    "POLICY_DECIDING", "REPLAYING", "CERTIFYING", "REPORTING",
    "MEMORY_CONSOLIDATING", "DONE",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Skill file loader
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_skill_metadata(skill_dir: Path) -> dict:
    """Parse structured metadata from a skill's SKILL.md header."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}
    text = skill_md.read_text(encoding="utf-8")
    metadata = {}
    for line in text.splitlines()[:20]:  # only check header area
        m = re.match(r'\*\*(\w+):\*\*\s*(.+)', line)
        if m:
            metadata[m.group(1).lower()] = m.group(2).strip()
    return metadata


def load_skill_text(skill_name: str, skills_dir: Path | None = None) -> str:
    """Load the full text of a skill's SKILL.md file."""
    if skills_dir is None:
        skills_dir = _SKILLS_DIR
    skill_path = skills_dir / skill_name
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return f"<!-- skill '{skill_name}' not found -->"
    return skill_md.read_text(encoding="utf-8")


def load_skill_metadata(skill_name: str, skills_dir: Path | None = None) -> dict:
    """Load parsed metadata from a skill's SKILL.md file."""
    if skills_dir is None:
        skills_dir = _SKILLS_DIR
    return _parse_skill_metadata(skills_dir / skill_name)


# ═══════════════════════════════════════════════════════════════════════════════
#  Progressive accumulation
# ═══════════════════════════════════════════════════════════════════════════════

def get_accumulated_skills(current_phase: str) -> list[str]:
    """Return the list of all skill names accumulated up to and including
    the current phase. Skills are returned in phase order, deduplicated."""
    accumulated: list[str] = []
    seen: set[str] = set()

    for phase in PHASE_ORDER:
        if phase not in PHASE_SKILL_MAP:
            continue  # unknown phase, skip
        for skill in PHASE_SKILL_MAP.get(phase, []):
            if skill not in seen:
                accumulated.append(skill)
                seen.add(skill)
        if phase == current_phase:
            break

    return accumulated


def get_accumulated_skill_texts(current_phase: str, skills_dir: Path | None = None) -> list[dict]:
    """Return the full skill texts accumulated up to the current phase.

    Returns a list of dicts: {"name": str, "phase": str, "role": str, "text": str}
    """
    if skills_dir is None:
        skills_dir = _SKILLS_DIR

    skill_names = get_accumulated_skills(current_phase)
    result = []
    for name in skill_names:
        metadata = load_skill_metadata(name, skills_dir)
        text = load_skill_text(name, skills_dir)
        result.append({
            "name": name,
            "phase": metadata.get("phase", ""),
            "role": metadata.get("role", ""),
            "text": text,
        })
    return result


def format_accumulated_context(current_phase: str, skills_dir: Path | None = None) -> str:
    """Format all accumulated skills as a single context block for agent injection."""
    skills = get_accumulated_skill_texts(current_phase, skills_dir)
    if not skills:
        return ""

    parts = [
        "## Accumulated Skills Context",
        f"Run phase: {current_phase}",
        "",
    ]

    for skill in skills:
        parts.append(f"### Skill: {skill['name']}")
        if skill["phase"]:
            parts.append(f"Phase: {skill['phase']}")
        if skill["role"]:
            parts.append(f"Role: {skill['role']}")
        parts.append("")
        parts.append(skill["text"])
        parts.append("")

    return "\n".join(parts)
