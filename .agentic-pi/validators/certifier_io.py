"""Pure IO/schema helpers for the certifier runner.

This module is intentionally authority-neutral. It provides shared file,
hashing, schema, and local-module-loading helpers only. It does not decide
policy and it does not write result artifacts by itself.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from validate_schema import validate as validate_schema_instance


AGENTIC_PI_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = AGENTIC_PI_ROOT / "schemas"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def schema_path(name: str) -> Path:
    return SCHEMA_DIR / name


def validate_with_schema(instance: Any, schema_name: str, label: str, failed: list) -> None:
    try:
        schema = load_json(schema_path(schema_name))
    except Exception as exc:
        failed.append(f"{label} schema load failed: {exc}")
        return
    for error in validate_schema_instance(instance, schema):
        failed.append(f"{label} schema validation failed: {error}")
