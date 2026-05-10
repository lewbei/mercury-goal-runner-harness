import json
from pathlib import Path

def render_final_status_md(json_path: Path, md_path: Path, certification: dict | None = None) -> None:
    """Render a human‑readable final_status.md from the machine‑readable final_status.json.

    Markdown is a derived view only. Machine authority remains final_status.json.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to read final_status.json at {json_path}: {exc}")

    status = data.get("status", "UNKNOWN")
    run_id = data.get("run_id", "")
    source = data.get("status_source", "")
    authority = data.get("final_status_authority", "certifier_only")
    can_certify_done = data.get("can_certify_done", False)
    policy_path = data.get("policy_decision_path", "")
    cert_path = data.get("certification_path", "")
    generated_at = data.get("generated_at", "")
    passed_checks = []
    failed_checks = []
    artifact_hashes = {}
    if certification:
        passed_checks = certification.get("passed_checks", [])
        failed_checks = certification.get("failed_checks", [])
        artifact_hashes = certification.get("artifact_hashes", {})

    lines = [
        f"# Final Status: {status}",
        "",
        f"Run ID: `{run_id}`",
        "",
        "## Authority",
        f"- final_status_authority: {authority}",
        f"- can_certify_done: {str(can_certify_done).lower()}",
        f"Status source: `{source}`",
        f"Policy decision path: `{policy_path}`",
        f"Certification path: `{cert_path}`",
        f"Generated at: {generated_at}",
        "",
        "## Passed checks",
    ]
    if passed_checks:
        lines.extend(f"- {item}" for item in passed_checks)
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Failed checks")
    if failed_checks:
        lines.extend(f"- {item}" for item in failed_checks)
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Artifact hashes")
    if artifact_hashes:
        lines.extend(f"- `{key}`: `{value}`" for key, value in artifact_hashes.items())
    else:
        lines.append("- none")

    md_path.write_text("\n".join(lines), encoding="utf-8")
