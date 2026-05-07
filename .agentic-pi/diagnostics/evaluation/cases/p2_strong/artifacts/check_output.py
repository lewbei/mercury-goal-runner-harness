from pathlib import Path

print(Path("artifacts/output.txt").read_text(encoding="utf-8").strip())
