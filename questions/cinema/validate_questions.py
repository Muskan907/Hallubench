import json
from pathlib import Path
from collections import Counter

path = Path("data/final/cinema/questions.jsonl")

total = 0
ids = set()
types = Counter()
errors = []

with path.open("r", encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        try:
            q = json.loads(line)

            required = [
                "question_id", "ground_truth_id", "domain",
                "question_type", "question",
                "accepted_answers", "evidence"
            ]

            for key in required:
                if key not in q:
                    errors.append(f"Line {line_no}: Missing {key}")

            qid = q.get("question_id")

            if qid in ids:
                errors.append(f"Line {line_no}: Duplicate ID {qid}")
            ids.add(qid)

            if not q.get("accepted_answers"):
                errors.append(f"Line {line_no}: Empty answer")

            if not q.get("evidence"):
                errors.append(f"Line {line_no}: Missing evidence")

            if q.get("domain") != "cinema":
                errors.append(f"Line {line_no}: Wrong domain")

            types[q.get("question_type")] += 1
            total += 1

        except Exception as e:
            errors.append(f"Line {line_no}: {e}")

print("\nCINEMA QUESTION VALIDATION")
print("Total questions:", total)
print("Unique IDs:", len(ids))
print("Question categories:", dict(types))
print("Errors:", len(errors))

for error in errors[:20]:
    print(error)

print("STATUS:", "PASS" if total == 50000 and not errors else "FAIL")
