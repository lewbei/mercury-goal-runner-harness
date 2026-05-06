from pathlib import Path

p = Path("docs/V0_1_USAGE.md")
text = p.read_text(encoding="utf-8", errors="replace")

replacements = {
    "ΓÇô": "-",
    "ΓÇæ": "-",
    "ΓÇÖ": "'",
    "ΓÇ»": " ",
    "ΓÇ£": "\"",
    "ΓÇ¥": "\""
}

for bad, good in replacements.items():
    text = text.replace(bad, good)

p.write_text(text, encoding="utf-8")
print("Cleaned docs/V0_1_USAGE.md")