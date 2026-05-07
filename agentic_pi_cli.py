"""Console-script wrapper for the local harness CLI."""
from pathlib import Path
import importlib.util
import sys


def _load_cli_module():
    cli_path = Path(__file__).resolve().parent / ".agentic-pi" / "runtime" / "pi_cli.py"
    spec = importlib.util.spec_from_file_location("agentic_pi_runtime_cli", cli_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    return _load_cli_module().main()


if __name__ == "__main__":
    sys.exit(main())
