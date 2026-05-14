#!/usr/bin/env python3
"""Canonical JSON helpers for deterministic runtime evidence.

The helpers are deliberately small and mechanical. They do not certify DONE,
decide policy, or grant authority. They only serialize JSON in one stable form
and verify that written bytes match the canonical bytes that were intended.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


CANONICAL_JSON_VERSION = "canonical_json_v1"


def stable_json(data: Any) -> str:
    """Return the canonical JSON text used by the bounded runtime slices."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def canonical_json_bytes(data: Any) -> bytes:
    """Return canonical JSON bytes with the required trailing newline."""
    return (stable_json(data) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(data: Any) -> str:
    return sha256_bytes(stable_json(data).encode("utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_canonical(
    path: Path,
    data: Any,
    protected_name_checker: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Write canonical JSON and verify readback bytes.

    `protected_name_checker` lets authority-owning callers reject filenames such
    as final_status.json without importing their policy into this generic module.
    """
    if protected_name_checker is not None and protected_name_checker(path.name):
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    expected_bytes = canonical_json_bytes(data)
    path.write_bytes(expected_bytes)
    actual_bytes = path.read_bytes()
    if actual_bytes != expected_bytes:
        raise IOError(f"canonical JSON readback mismatch: {path}")
    digest = sha256_bytes(actual_bytes)
    return {
        "writer": CANONICAL_JSON_VERSION,
        "path": str(path),
        "sha256": digest,
        "byte_count": len(actual_bytes),
        "readback_verified": True,
    }
