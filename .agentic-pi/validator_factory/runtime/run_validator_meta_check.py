#!/usr/bin/env python3
"""Meta-check for generated validators.

Checks that a validator spec is self-consistent and that the validator
code follows basic safety rules before any fixture tests are run.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


_VF_DIR = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_meta_check(validator_spec: dict, validator_code_path: Optional[Path] = None) -> list[dict]:
    """Run meta-checks on a validator spec and optional code.

    Returns list of check results:
    {
        "check": str,
        "passed": bool,
        "detail": str
    }
    """
    results = []

    # 1. Schema validation
    try:
        schema = _load_json(_VF_DIR / "validator_spec.schema.json")
        validators_dir = _VF_DIR.parent / "validators"
        if str(validators_dir) not in sys.path:
            sys.path.insert(0, str(validators_dir))
        from validate_schema import validate
        schema_errors = validate(validator_spec, schema)
        results.append({
            "check": "schema_valid",
            "passed": len(schema_errors) == 0,
            "detail": "Schema valid" if not schema_errors else f"Schema errors: {schema_errors}",
        })
    except Exception as e:
        results.append({"check": "schema_valid", "passed": False, "detail": str(e)})

    # 2. Authority level is known
    level = validator_spec.get("authority_level", "")
    known_levels = {"V0_PROPOSED", "V1_LOCAL_TESTED", "V2_INDEPENDENT_TESTED",
                    "V3_EXTERNAL_TRUSTED", "V4_CORE_TRUSTED"}
    results.append({
        "check": "authority_level_known",
        "passed": level in known_levels,
        "detail": f"Authority level: {level}" if level in known_levels else f"Unknown level: {level}",
    })

    # 3. Success criteria are listed
    sc = validator_spec.get("success_criteria", [])
    results.append({
        "check": "has_success_criteria",
        "passed": len(sc) > 0,
        "detail": f"{len(sc)} success criteria listed" if sc else "No success criteria listed",
    })

    # 4. Runtime command is specified
    cmd = validator_spec.get("runtime_command", "")
    results.append({
        "check": "has_runtime_command",
        "passed": bool(cmd),
        "detail": f"Command: {cmd}" if cmd else "No runtime command specified",
    })

    # 5. Code safety scan (if code path provided)
    if validator_code_path and validator_code_path.exists():
        code = validator_code_path.read_text(encoding="utf-8", errors="replace")

        # Check for dangerous patterns
        dangerous_patterns = [
            ("os.system(", "Uses os.system() - shell injection risk"),
            ("subprocess.Popen(", "Uses subprocess.Popen() without shell=False"),
            ("eval(", "Uses eval() - code injection risk"),
            ("exec(", "Uses exec() - code injection risk"),
            ("__import__(", "Uses dynamic import"),
        ]
        for pattern, warning in dangerous_patterns:
            if pattern in code:
                results.append({
                    "check": f"code_safety_{pattern.strip('(')}",
                    "passed": False,
                    "detail": warning,
                })

        # Check for always-pass pattern
        if "return True" in code and "return False" not in code:
            results.append({
                "check": "code_always_pass",
                "passed": False,
                "detail": "Validator code returns True without any False path - may be always-pass",
            })

        # Check that the code has a main check function
        if "def check" not in code and "def validate" not in code and "def run" not in code:
            results.append({
                "check": "code_has_check_function",
                "passed": False,
                "detail": "No 'def check', 'def validate', or 'def run' found in code",
            })

        # If no safety issues found:
        safety_checks = [r for r in results if r["check"].startswith("code_safety_") or
                          r["check"] in ("code_always_pass", "code_has_check_function")]
        if not any(not r["passed"] for r in safety_checks):
            results.append({
                "check": "code_safety",
                "passed": True,
                "detail": "No dangerous patterns detected",
            })

    return results


def all_meta_checks_pass(results: list[dict]) -> bool:
    """Return True if all meta checks passed."""
    return all(r["passed"] for r in results)
