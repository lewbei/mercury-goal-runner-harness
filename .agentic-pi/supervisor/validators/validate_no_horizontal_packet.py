"""Blocks work packets that expand horizontally before vertical slice is proven."""
import json, sys
from pathlib import Path

def validate(packet_path: Path, proven_slices: list) -> dict:
    packet = json.loads(packet_path.read_text())
    files = packet.get("files_approx", 1)
    layers = packet.get("end_to_end_layers", [])
    slice_id = packet.get("slice_id", "unknown")
    if len(layers) < 3 and files > 3:
        return {"blocked": True, "reason": f"Looks horizontal: {layers} layers but {files} files"}
    return {"blocked": False, "reason": ""}
