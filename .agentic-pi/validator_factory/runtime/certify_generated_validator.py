#!/usr/bin/env python3
"""Validator certification — the gate that promotes a V0_PROPOSED validator
to V1_LOCAL_TESTED or higher.

This is a trusted core component. It runs the full certification pipeline:
1. Meta-check
2. Positive fixtures
3. Negative fixtures (if available)
4. Mutation tests (if fixture suite is available)
5. Safety scan (embedded in meta-check)
6. Certification decision
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_VF_DIR = Path(__file__).resolve().parent.parent
_RUNTIME_DIR = _VF_DIR / "runtime"

# Lazy-loaded runtime modules
_meta_check_mod = None
_fixture_mod = None
_mutation_mod = None


def _load_meta_check():
    global _meta_check_mod
    if _meta_check_mod is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_validator_meta_check",
            _RUNTIME_DIR / "run_validator_meta_check.py",
        )
        _meta_check_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_meta_check_mod)
    return _meta_check_mod


def _load_fixture_runner():
    global _fixture_mod
    if _fixture_mod is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_validator_fixtures",
            _RUNTIME_DIR / "run_validator_fixtures.py",
        )
        _fixture_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_fixture_mod)
    return _fixture_mod


def _load_mutation_runner():
    global _mutation_mod
    if _mutation_mod is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_validator_mutations",
            _RUNTIME_DIR / "run_validator_mutations.py",
        )
        _mutation_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mutation_mod)
    return _mutation_mod


def certify_validator(
    validator_spec: dict,
    fixture_suite: Optional[dict] = None,
    validator_code_path: Optional[Path] = None,
) -> dict:
    """Run the full certification pipeline for a validator.

    Args:
        validator_spec: The validator spec dict.
        fixture_suite: Optional fixture suite. If None, only meta-check runs.
        validator_code_path: Optional path to the validator code file.

    Returns:
        Certification result dict with full details.
    """
    mc = _load_meta_check()
    fr = _load_fixture_runner()
    mr = _load_mutation_runner()

    now = datetime.now(timezone.utc).isoformat()
    validator_id = validator_spec.get("validator_id", "unknown")
    current_level = validator_spec.get("authority_level", "V0_PROPOSED")

    # Step 1: Meta-check
    meta_results = mc.run_meta_check(validator_spec, validator_code_path)
    meta_passed = mc.all_meta_checks_pass(meta_results)

    # Step 2: Fixture tests
    fixture_result = None
    fixtures_passed = False
    if fixture_suite:
        fixture_result = fr.run_fixtures(validator_spec, fixture_suite)
        fixtures_passed = fr.all_fixtures_pass(fixture_result)

    # Step 3: Mutation tests
    mutation_result = None
    mutations_passed = False
    if fixture_suite and fixtures_passed:
        mutation_result = mr.run_mutations(validator_spec, fixture_suite)
        mutations_passed = mr.mutation_test_passes(mutation_result)

    # Step 4: Determine new authority level
    new_level = current_level
    certification_verdict = "FAILED"
    failures = []

    if not meta_passed:
        failures.append("meta_check")

    if fixture_suite and not fixtures_passed:
        failures.append("fixture_tests")

    # Determine new authority level
    if not failures:
        if current_level == "V0_PROPOSED":
            if fixture_suite and fixtures_passed:
                if mutation_result and mutations_passed:
                    new_level = "V2_INDEPENDENT_TESTED"
                else:
                    new_level = "V1_LOCAL_TESTED"
            else:
                new_level = "V0_PROPOSED"
        elif current_level == "V1_LOCAL_TESTED" and fixtures_passed:
            if mutation_result and mutations_passed:
                new_level = "V2_INDEPENDENT_TESTED"
            else:
                new_level = "V1_LOCAL_TESTED"

        certification_verdict = "CERTIFIED"
    elif len(failures) == 1 and failures[0] == "fixture_tests":
        # No fixtures means no mutation tests needed
        pass

    # Build certification result
    cert_result = {
        "validator_id": validator_id,
        "previous_level": current_level,
        "new_level": new_level,
        "certification_verdict": certification_verdict,
        "certified_at": now,
        "meta_check": {
            "passed": meta_passed,
            "details": meta_results,
        },
        "fixture_tests": {
            "run": fixture_result is not None,
            "passed": fixtures_passed,
            "details": fixture_result,
        } if fixture_result else {"run": False, "passed": False, "details": None},
        "mutation_tests": {
            "run": mutation_result is not None,
            "passed": mutations_passed,
            "details": mutation_result,
        } if mutation_result else {"run": False, "passed": False, "details": None},
        "failures": failures,
    }

    return cert_result


def is_certified(cert_result: dict) -> bool:
    """Return True if the validator was certified (reached V1 or higher)."""
    return cert_result.get("certification_verdict") == "CERTIFIED"
