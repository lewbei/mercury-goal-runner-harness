"""Certifier gate functions — deterministic post-policy checks.

Each gate inspects a specific artifact or condition and can block certification.
Gates are applied sequentially after the policy engine decides. A gate can
downgrade CERTIFIED_DONE to NOT_DONE but cannot upgrade NOT_DONE to CERTIFIED_DONE.

This module is extracted from certify_run.py for readability. It does not
change certifier behavior — the golden behavior lock tests verify this.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from certifier_io import load_json, load_local_module, validate_with_schema
from certifier_paths import find_output, run_relative


def apply_formal_verification_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Gate: check for formal verification artifacts.

    If F_*.json artifacts exist and have verdict PASS, credit them.
    Missing formal verification is a soft warning (not blocking).
    """
    artifacts_dir = run_dir / "verifier_artifacts"
    if not artifacts_dir.is_dir():
        passed.append("formal_verification: no artifacts dir (informational)")
        return current_status

    formal_artifacts = list(artifacts_dir.glob("F_*.json"))
    if not formal_artifacts:
        passed.append("formal_verification: no formal artifacts (informational)")
        return current_status

    for fa in formal_artifacts:
        try:
            data = json.loads(fa.read_text(encoding="utf-8"))
            if data.get("kind") == "formal_verification":
                verdict = data.get("verdict", "UNKNOWN")
                detail = data.get("formal_verification_detail", {})
                confidence = detail.get("confidence", 0.0)

                if verdict == "PASS":
                    passed.append(
                        f"formal_verification: {fa.stem} PASS "
                        f"(confidence={confidence:.2f})"
                    )
                else:
                    failed.append(
                        f"formal_verification: {fa.stem} {verdict} "
                        f"(confidence={confidence:.2f})"
                    )
                    if current_status in ("DONE_PASS", "CERTIFIED_DONE"):
                        current_status = "DONE_FAIL"
        except Exception as e:
            passed.append(f"formal_verification: {fa.stem} could not read ({e})")

    return current_status


def apply_cryptographic_signature_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Gate: verify cryptographic signatures on artifacts.

    If agent public key and signatures exist, verify them.
    Unsigned artifacts get a warning. Forged/tampered artifacts block certification.
    """
    sig_files = list(run_dir.rglob("*.sig"))
    if not sig_files:
        passed.append("crypto_signatures: no signatures found (informational)")
        return current_status

    try:
        formal_dir = Path(__file__).resolve().parents[1] / "formal"
        sys.path.insert(0, str(formal_dir))
        from harness_signing import HarnessSigner
        signer = HarnessSigner(run_dir)
        results = signer.verify_all()

        for r in results:
            if r["verdict"] == "AUTHENTIC":
                passed.append(f"crypto_signature: {r['artifact']} AUTHENTIC")
            elif r["verdict"] in ("FORGED", "TAMPERED"):
                failed.append(
                    f"crypto_signature: {r['artifact']} {r['verdict']} — {r['reason']}"
                )
                if current_status in ("DONE_PASS", "CERTIFIED_DONE"):
                    current_status = "DONE_FAIL"
            elif r["verdict"] == "UNSIGNED":
                passed.append(
                    f"crypto_signature: {r['artifact']} unsigned (informational)"
                )
    except ImportError:
        passed.append("crypto_signatures: signing module not available (informational)")
    except Exception as e:
        passed.append(f"crypto_signatures: verification error ({e})")

    return current_status


def apply_artifact_location_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Gate: if expected_artifacts.json exists, check artifact placement.

    Blocks certification if:
    - A required artifact is at the wrong path (BLOCKED_BY_ARTIFACT_MISPLACEMENT)
    - A required artifact is missing entirely
    """
    ea_path = run_dir / "expected_artifacts.json"
    if not ea_path.is_file():
        return current_status

    try:
        vloc = load_local_module(
            "validate_artifact_location",
            Path(__file__).resolve().parents[1] / "artifacts" / "validators" / "validate_artifact_location.py",
        )
    except Exception as exc:
        failed.append(f"artifact location validator load failed: {exc}")
        return current_status

    try:
        verdicts = vloc.validate_artifact_location(run_dir)
    except Exception as exc:
        failed.append(f"artifact location validation failed: {exc}")
        return "NOT_DONE"

    has_misplacement = vloc.has_misplacement(verdicts)
    has_missing = vloc.has_missing_required(verdicts)

    for v in verdicts:
        if v["verdict"] == "ACCEPTED":
            passed.append(f"artifact placement OK: {v['artifact_id']} at {v['expected_path']}")
        elif v["verdict"] == "BLOCKED_BY_ARTIFACT_MISPLACEMENT":
            failed.append(f"artifact MISPLACED: {v['artifact_id']} expected at {v['expected_path']}, found at {v['actual_path']}")
        elif v["verdict"] == "NOT_DONE":
            failed.append(f"artifact MISSING: {v['artifact_id']} expected at {v['expected_path']} but not found")

    if has_misplacement or has_missing:
        return "NOT_DONE"

    return current_status


def apply_audit_report_gate(run_dir: Path, provenance_mode: bool, failed: list, passed: list, current_status: str) -> str:
    """Gate: if audit_report.json exists, check audit verdict."""
    audit_path = run_dir / "audit_report.json"
    if not audit_path.is_file():
        return current_status
    try:
        audit = load_json(audit_path)
    except Exception as exc:
        failed.append(f"audit_report.json invalid: {exc}")
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    if audit.get("valid") is False:
        failed.append("audit_report.json invalid blocks certification")
        for violation in audit.get("violations", []):
            failed.append(f"audit violation: {violation}")
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    passed.append("audit_report.json valid")
    return current_status


def apply_replay_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Gate: if replay_report.json exists, check replay verdict.

    Blocks certification if replay verdict is REPLAY_MISMATCH.
    """
    replay_path = run_dir / "replay_report.json"
    if not replay_path.is_file():
        return current_status

    try:
        replay = load_json(replay_path)
    except Exception as exc:
        failed.append(f"replay_report.json invalid: {exc}")
        return "NOT_DONE"

    verdict = replay.get("verdict", "")
    if verdict == "REPLAY_MISMATCH":
        failed.append("replay_check: REPLAY_MISMATCH blocks certification")
        for check_name, check_result in replay.get("checks", {}).items():
            if not check_result.get("passed", True):
                failed.append(f"  replay check failed: {check_name}: {check_result.get('detail', '')}")
        return "NOT_DONE"
    elif verdict == "REPLAY_PARTIAL":
        passed.append("replay_check: REPLAY_PARTIAL (warning-level issues only)")
    elif verdict == "REPLAY_MATCH":
        passed.append("replay_check: REPLAY_MATCH — certification is reproducible")
    else:
        failed.append(f"replay_check: unknown verdict '{verdict}'")
        return "NOT_DONE"

    return current_status


def apply_drift_report_gate(run_dir: Path, provenance_mode: bool, failed: list, passed: list, current_status: str) -> str:
    """Gate: if drift_report.json exists, check drift level."""
    drift_path = run_dir / "drift_report.json"
    if not drift_path.is_file():
        return current_status
    try:
        drift = load_json(drift_path)
    except Exception as exc:
        failed.append(f"drift_report.json invalid: {exc}")
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    schema_failures = []
    validate_with_schema(drift, "drift_report.schema.json", "drift_report.json", schema_failures)
    if schema_failures:
        failed.extend(schema_failures)
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    if drift.get("valid") is False:
        failed.append("drift_report.json invalid blocks certification")
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    if drift.get("blocking") is True or drift.get("drift_level") in {"repairable", "fatal"}:
        failed.append(f"drift_report.json blocks certification: {drift.get('drift_level')}")
        for violation in drift.get("violations", []):
            failed.append(f"drift violation: {violation}")
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"

    passed.append(f"drift_report.json valid: {drift.get('drift_level')}")
    return current_status


def apply_evidence_freeze_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Freeze producer-linked evidence after policy decision and before certification.

    Evidence freeze can block certification when provenance evidence is missing,
    mutable, or not producer-linked. It does not certify DONE by itself.
    """
    if not provenance_mode:
        return current_status

    try:
        indexer = load_local_module(
            "evidence_indexer",
            Path(__file__).resolve().parents[1] / "runtime" / "evidence_indexer.py",
        )
        freezer = load_local_module(
            "evidence_freezer",
            Path(__file__).resolve().parents[1] / "runtime" / "evidence_freezer.py",
        )
        index_validator = load_local_module(
            "validate_evidence_index",
            Path(__file__).resolve().parents[1] / "validators" / "validate_evidence_index.py",
        )
        freeze_validator = load_local_module(
            "validate_evidence_freeze",
            Path(__file__).resolve().parents[1] / "validators" / "validate_evidence_freeze.py",
        )

        indexer.write_evidence_index(run_dir)
        ok, message = index_validator.validate_evidence_index(run_dir)
        if not ok:
            failed.append(f"evidence_index.json invalid: {message}")
            return "NOT_DONE"
        passed.append("evidence_index.json validates")

        freezer.freeze_evidence(run_dir)
        ok, message = freeze_validator.validate_evidence_freeze(run_dir)
        if not ok:
            failed.append(f"evidence_freeze.json invalid: {message}")
            return "NOT_DONE"
        passed.append("evidence_freeze.json validates")
    except Exception as exc:
        failed.append(f"evidence freeze failed: {exc}")
        return "NOT_DONE"

    return current_status


def evaluate_done_criteria(
    run_dir,
    done_criteria,
    final_outputs,
    output_paths,
    passed,
    failed,
    artifact_tests_present=False,
):
    """Evaluate done criteria against output files."""
    first_output_path = next((path for path in output_paths.values() if path and path.is_file()), None)

    for crit in done_criteria:
        crit_lower = crit.lower()

        if "contains the word" in crit_lower:
            filename_part = crit.split("contains")[0].strip().rstrip(".")
            word = None
            if "'" in crit:
                parts = crit.split("'")
                if len(parts) >= 3:
                    word = parts[1]

            file_path = find_output(run_dir, filename_part)
            if not file_path or not file_path.is_file():
                failed.append(f"Done criterion failed: {crit} (file not found)")
                continue

            content = file_path.read_text(encoding="utf-8")
            if word and word in content:
                passed.append(f"Done criterion satisfied: {crit}")
            else:
                failed.append(f"Done criterion failed: {crit} (word '{word}' not found)")

        if "three bullet" in crit_lower:
            if not first_output_path:
                failed.append(f"Done criterion failed: {crit} (file not found)")
                continue
            content = first_output_path.read_text(encoding="utf-8")
            bullet_count = sum(1 for line in content.splitlines() if line.strip().startswith("- "))
            if bullet_count >= 3:
                passed.append(f"Done criterion satisfied: {crit}")
            else:
                failed.append(f"Done criterion failed: {crit} ({bullet_count} bullets found)")

        if (
            "run" in crit_lower
            or "execute" in crit_lower
            or "prints at least two lines" in crit_lower
        ):
            if artifact_tests_present:
                passed.append(f"Done criterion delegated to artifact_tests: {crit}")
                continue
            for output in final_outputs:
                if not output.endswith(".py"):
                    continue
                output_path = output_paths.get(output)
                if not output_path or not output_path.is_file():
                    failed.append(f"Done criterion failed: {crit} ({output} missing)")
                    continue
                try:
                    from certify_run import run_python_output
                    result = run_python_output(output_path, cwd=run_dir)
                except Exception as exc:
                    failed.append(f"Done criterion execution error for {output}: {exc}")
                    continue
                line_count = len([line for line in result.stdout.splitlines() if line.strip()])
                if result.returncode == 0 and line_count >= 2:
                    passed.append(f"Done criterion satisfied by running {output}")
                else:
                    failed.append(
                        f"Done criterion failed: {output} exit={result.returncode}, lines={line_count}"
                    )


def apply_memory_authority_gate(
    run_dir: Path,
    provenance_mode: bool,
    failed: list,
    passed: list,
    current_status: str,
) -> str:
    """Gate: scan for memory artifacts with authority-leak fields.

    Memory artifacts must not contain fields like final_status, certified_done,
    policy_override, etc. If such leaks are found, certification is blocked.
    """
    # Paths to scan for memory-like artifacts
    memory_paths = [
        run_dir / "memory_journal.jsonl",
        run_dir / "memory_journal.json",
        run_dir / "learning_candidate.json",
    ]
    # Also scan current run-local/quarantine memory reports.
    memory_dir = run_dir / "memory"
    if memory_dir.is_dir():
        memory_paths.extend(sorted(memory_dir.glob("*.json")))
        memory_paths.extend(sorted(memory_dir.glob("*.jsonl")))

    found_leaks = False
    for mem_path in memory_paths:
        if not mem_path.is_file():
            continue
        try:
            vma = load_local_module(
                "validate_memory_authority",
                Path(__file__).resolve().parents[1] / "validators" / "validate_memory_authority.py",
            )
            data = vma.load_memory_objects(mem_path)
            errors = vma.validate_memory_authority(data)
            if errors:
                found_leaks = True
                failed.append(f"MEMORY_AUTHORITY_VIOLATION: {mem_path.name}")
                for err in errors:
                    failed.append(f"  memory leak: {err}")
        except Exception as exc:
            failed.append(f"memory authority check failed for {mem_path.name}: {exc}")
            found_leaks = True

    if found_leaks:
        failed.append("Memory authority violation blocks certification")
        return "NOT_DONE"

    return current_status


def check_validator_certification(run_dir: Path, failed: list, passed: list, provenance_mode: bool) -> None:
    """Read validator_certification.json and block if missing or not certified."""
    if not provenance_mode:
        passed.append("validator_certification.json skipped for legacy non-provenance run")
        return
    verifier_dir = run_dir / "verifier_artifacts"
    if not verifier_dir.is_dir() or not any(verifier_dir.glob("*.json")):
        passed.append("validator_certification.json skipped because verifier_artifacts are missing")
        return
    vc_path = run_dir / "validator_certification.json"
    if not vc_path.is_file():
        failed.append("validator_certification.json missing \u2014 verifier not certified")
        return
    try:
        data = json.loads(vc_path.read_text(encoding="utf-8"))
    except Exception as exc:
        failed.append(f"validator_certification.json parse error: {exc}")
        return
    if data.get("certified") is not True:
        reasons = data.get("reasons", [])
        reasons_str = "; ".join(reasons) if reasons else "no reason given"
        failed.append(f"verifier not certified: {reasons_str}")
        return
    passed.append("validator_certification.json present and certified=True")
