import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/raw/scientists/openalex_authors.jsonl"
OUTPUT = ROOT / "data/raw/scientists/orcid_ids.txt"

ids = set()

with SOURCE.open(encoding="utf-8") as f:
    for line in f:
        record = json.loads(line)
        orcid = record.get("orcid")

        if orcid:
            ids.add(orcid.rstrip("/").split("/")[-1])

OUTPUT.write_text(
    "\n".join(sorted(ids)),
    encoding="utf-8"
)

print(f"Extracted {len(ids)} unique ORCID IDs.")
print(f"Saved to: {OUTPUT}")