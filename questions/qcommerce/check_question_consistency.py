import json
from pathlib import Path
from collections import Counter

path = Path("data/final/qcommerce/questions.jsonl")

counts = Counter()
mismatches = Counter()
examples = {}

with path.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        row = json.loads(line)
        qtype = row["question_type"]

        counts[qtype] += 1

        if row["evidence"] not in row["accepted_answers"]:
            mismatches[qtype] += 1
            examples.setdefault(qtype, row)

print("QUESTION TYPE VALIDATION")
print("=" * 45)

for qtype, count in counts.items():
    print(f"\n{qtype}")
    print("Total:", count)
    print("Evidence not in accepted answers:", mismatches[qtype])

    if qtype in examples:
        print("Example accepted answers:", examples[qtype]["accepted_answers"])
        print("Example evidence:", examples[qtype]["evidence"])

print("\nInterpretation:")
print("Evidence-retrieval and reviewer-report questions should accept their evidence.")
print("Verification-boundary questions intentionally use a different answer.")
