import json
import sys
from pathlib import Path

VALID_STATUSES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def _load_schema_validator():
    validators_dir = Path(__file__).resolve().parent
    if str(validators_dir) not in sys.path:
        sys.path.insert(0, str(validators_dir))
    from validate_schema import validate as validate_schema_instance

    return validate_schema_instance


def _load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def authoritative_status(run_dir: Path) -> str:
    """Read machine authority from final_status.json, never final_status.md."""
    final_status_path = run_dir / "final_status.json"
    data = load_json(final_status_path)
    return data["status"]


def validate_data(final_status: dict, run_dir: Path) -> list[str]:
    errors = []
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "final_status.schema.json"
    schema = _load_schema(schema_path)
    validate_schema_instance = _load_schema_validator()
    errors.extend(
        f"final_status.json schema validation failed: {error}"
        for error in validate_schema_instance(final_status, schema)
    )

    status = final_status.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"final_status.json status is not valid: {status}")
    if final_status.get("final_status_authority") != "certifier_only":
        errors.append("final_status.json authority must be certifier_only")
    if final_status.get("can_certify_done") is not False:
        errors.append("final_status.json can_certify_done must be false")

    cert_path = run_dir / "certification.json"
    if cert_path.is_file():
        certification = load_json(cert_path)
        if certification.get("status") != status:
            errors.append("certification.json status does not match final_status.json status")
    else:
        errors.append("certification.json missing for final_status.json validation")

    policy_path = run_dir / "policy_decision.json"
    if policy_path.is_file():
        policy = load_json(policy_path)
        if policy.get("status") != status:
            errors.append("policy_decision.json status does not match final_status.json status")
        if final_status.get("status_source") != "policy_decision.json":
            errors.append("provenance run final_status.json must cite policy_decision.json")
    elif final_status.get("status_source") != "certification.json":
        errors.append("non-provenance run final_status.json must cite certification.json")

    return errors


def validate(final_status_path: Path, run_dir: Path, passed: list, failed: list) -> None:
    """Validate final_status.json against its schema and ensure consistency with
    certification.json and policy_decision.json (if present).
    The `passed` and `failed` lists are mutated in‑place for reporting.
    """
    # Load final_status.json
    try:
        final_status = json.loads(final_status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        failed.append(f"final_status.json load failed: {exc}")
        return

    errors = validate_data(final_status, run_dir)
    if errors:
        failed.extend(errors)
    else:
        passed.append("final_status.json validated")
