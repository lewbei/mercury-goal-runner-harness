#!/usr/bin/env python3
"""Deterministic transition validator for the Run Kernel.

This is a trusted core component. Only the Run Kernel calls this to
validate phase transitions. The validator never writes state.
"""

import json
from pathlib import Path
from typing import Optional


_RUN_KERNEL_DIR = Path(__file__).resolve().parent
_TRANSITION_RULES_PATH = _RUN_KERNEL_DIR / "transition_rules.json"
_PHASE_REGISTRY_PATH = _RUN_KERNEL_DIR / "phase_registry.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_transition_rules() -> list[dict]:
    """Load and return the transition rules list."""
    data = _load_json(_TRANSITION_RULES_PATH)
    return data.get("transitions", [])


def load_phase_registry() -> list[dict]:
    """Load and return the phase registry list."""
    data = _load_json(_PHASE_REGISTRY_PATH)
    return data.get("phases", [])


def _build_transition_map(rules: list[dict]) -> dict[str, set[str]]:
    """Build a map of from_phase -> set of allowed to_phases.

    A null from means the transition is allowed from any phase.
    """
    transition_map: dict[str, set[str]] = {}
    wildcard_entries: set[str] = set()
    for rule in rules:
        from_phase = rule.get("from")
        to_phase = rule.get("to")
        if from_phase is None:
            wildcard_entries.add(to_phase)
        else:
            transition_map.setdefault(from_phase, set()).add(to_phase)
    return transition_map, wildcard_entries


def validate_transition(
    current_phase: str,
    target_phase: str,
    transition_map: Optional[dict[str, set[str]]] = None,
    wildcard_entries: Optional[set[str]] = None,
) -> list[str]:
    """Validate whether a transition from current_phase to target_phase is legal.

    Returns a list of error strings. An empty list means the transition is valid.
    """
    errors: list[str] = []

    if transition_map is None or wildcard_entries is None:
        rules = load_transition_rules()
        transition_map, wildcard_entries = _build_transition_map(rules)

    # Check wildcard transitions (allowed from any phase)
    if target_phase in wildcard_entries:
        return errors  # valid

    # Check explicit transitions
    allowed = transition_map.get(current_phase, set())
    if target_phase in allowed:
        return errors  # valid

    errors.append(
        f"Transition from '{current_phase}' to '{target_phase}' is not allowed "
        f"by transition_rules.json."
    )
    return errors


def validate_phase_name(
    phase: str,
    registry: Optional[list[dict]] = None,
) -> list[str]:
    """Validate that a phase name exists in the phase registry."""
    errors: list[str] = []
    if registry is None:
        registry = load_phase_registry()

    known_phases = {entry["phase"] for entry in registry}
    if phase not in known_phases:
        errors.append(f"Unknown phase '{phase}'. Must be one of: {sorted(known_phases)}")
    return errors


def validate_transition_with_registry(
    current_phase: str,
    target_phase: str,
) -> list[str]:
    """Combined validation: check both phases exist and transition is legal."""
    errors: list[str] = []
    registry = load_phase_registry()
    rules = load_transition_rules()
    transition_map, wildcard_entries = _build_transition_map(rules)

    errors.extend(validate_phase_name(current_phase, registry))
    errors.extend(validate_phase_name(target_phase, registry))
    if not errors:
        errors.extend(validate_transition(current_phase, target_phase, transition_map, wildcard_entries))

    return errors
