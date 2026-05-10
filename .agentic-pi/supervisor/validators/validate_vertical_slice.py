"""Validates that a work packet is a true vertical slice, not horizontal."""
import json, sys
from pathlib import Path

def validate(packet_path: Path) -> dict:
    packet = json.loads(packet_path.read_text())
    issues = []
    if not packet.get("fixture"):
        issues.append("no fixture")
    if not packet.get("expected_verdict"):
        issues.append("no expected_verdict")
    layers = packet.get("end_to_end_layers", [])
    if len(layers) < 3:
        issues.append(f"only {len(layers)} layers, need >= 3")
    return {"valid": len(issues)==0, "issues": issues}

if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(json.dumps(validate(p), indent=2))
