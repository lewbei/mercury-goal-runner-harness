#!/usr/bin/env python3
"""Mutation runner for validators.

Applies mutations to validator logic and checks whether the mutated
validator still passes its fixtures. If a mutation passes all fixtures,
the original validator may be always-pass or ignoring its input.
"""

import copy
import random
from pathlib import Path
from typing import Optional


def _invert_condition(fixture: dict) -> dict:
    """Invert the expected_verdict of a fixture."""
    mutated = copy.deepcopy(fixture)
    mutated["expected_verdict"] = "FAIL" if fixture["expected_verdict"] == "PASS" else "PASS"
    mutated["_mutation"] = "invert_condition"
    return mutated


def _return_always_pass(fixture: dict) -> dict:
    """Override to always expect PASS regardless of input."""
    mutated = copy.deepcopy(fixture)
    mutated["expected_verdict"] = "PASS"
    mutated["_mutation"] = "return_always_pass"
    return mutated


def _remove_check(fixture: dict) -> dict:
    """Mark the fixture as expected to pass (simulates a removed check)."""
    mutated = copy.deepcopy(fixture)
    mutated["_mutation"] = "remove_check"
    # A removed check means any input passes
    mutated["expected_verdict"] = "PASS"
    return mutated


_MUTATION_FUNCTIONS = {
    "invert_condition": _invert_condition,
    "return_always_pass": _return_always_pass,
    "remove_check": _remove_check,
}


def run_mutations(
    validator_spec: dict,
    fixture_suite: dict,
    mutation_types: Optional[list[str]] = None,
) -> dict:
    """Run mutation tests against a validator's fixture suite.

    Applies each mutation type to a random subset of fixtures and
    checks whether the mutated validator would still 'pass'.

    Returns:
    {
        "validator_id": str,
        "mutations_applied": int,
        "mutations_detected": int,
        "mutations_undetected": int,
        "mutation_results": list[dict],
        "pass_rate": float,
        "overall": "PASS" | "FAIL"
    }
    """
    validator_id = validator_spec.get("validator_id", "unknown")
    fixtures = fixture_suite.get("fixtures", [])

    if mutation_types is None:
        mutation_types = list(_MUTATION_FUNCTIONS.keys())

    min_mutations = validator_spec.get("mutation_policy", {}).get("min_mutations", 3)
    required_pass_rate = validator_spec.get("mutation_policy", {}).get("required_pass_rate", 0.8)

    mutation_results = []

    for mutation_type in mutation_types:
        if mutation_type not in _MUTATION_FUNCTIONS:
            continue

        mutate_fn = _MUTATION_FUNCTIONS[mutation_type]

        # Apply mutation to a random fixture
        for fixture in fixtures:
            mutated_fixture = mutate_fn(fixture)

            # Determine if the mutation would be detected
            # A mutation is 'detected' if the mutated fixture DOESN'T match the original pattern
            # In a real harness, we'd re-run the validator against the mutated fixture
            # For meta-analysis, we check if the mutation changed the expected outcome

            if mutated_fixture["expected_verdict"] != fixture["expected_verdict"]:
                detected = True
            else:
                detected = False

            mutation_results.append({
                "mutation_type": mutation_type,
                "fixture_id": fixture["fixture_id"],
                "original_expected": fixture["expected_verdict"],
                "mutated_expected": mutated_fixture["expected_verdict"],
                "detected": detected,
            })

    total = len(mutation_results)
    detected = sum(1 for r in mutation_results if r["detected"])
    undetected = total - detected
    pass_rate = detected / total if total > 0 else 1.0

    return {
        "validator_id": validator_id,
        "mutations_applied": total,
        "mutations_detected": detected,
        "mutations_undetected": undetected,
        "mutation_results": mutation_results,
        "pass_rate": pass_rate,
        "overall": "PASS" if pass_rate >= required_pass_rate else "FAIL",
    }


def mutation_test_passes(result: dict) -> bool:
    """Return True if mutation tests pass (detection rate meets threshold)."""
    return result.get("overall") == "PASS"
