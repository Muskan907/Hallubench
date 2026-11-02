import json
import random
from pathlib import Path
from collections import Counter

SOURCE = Path("data/final/cinema/questions.jsonl")
OUT = Path("data/final/cinema")

random.seed(42)

quotas = {
    "movie_information": 20,
    "temporal": 10,
    "numerical": 30,
    "director_relationship": 6,
    "writer_relationship": 6,
    "cast_relationship": 20,
    "regional_language": 8
}

groups = {category: [] for category in quotas}

print("Loading validated cinema questions...")

with SOURCE.open("r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        category = q["question_type"]

        if category in groups:
            groups[category].append(q)

pilot = []

for category, quota in quotas.items():
    available = groups[category]

    if len(available) < quota:
        raise ValueError(f"Insufficient questions for {category}")

    pilot.extend(random.sample(available, quota))

random.shuffle(pilot)

output = OUT / "pilot_sample_100.json"

with output.open("w", encoding="utf-8") as f:
    json.dump(pilot, f, indent=2, ensure_ascii=False)

summary = {
    "domain": "cinema",
    "sample_size": len(pilot),
    "random_seed": 42,
    "sampling_method": "stratified_random_sampling",
    "category_quotas": quotas,
    "actual_category_counts": dict(
        Counter(q["question_type"] for q in pilot)
    ),
    "unique_question_ids": len(set(q["question_id"] for q in pilot)),
    "unique_ground_truth_ids": len(set(q["ground_truth_id"] for q in pilot))
}

with (OUT / "pilot_sample_summary.json").open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\nPILOT SAMPLE CREATED")
print("Total questions:", len(pilot))
print("Category counts:", summary["actual_category_counts"])
print("Unique question IDs:", summary["unique_question_ids"])
print("Unique ground-truth IDs:", summary["unique_ground_truth_ids"])
print("Output:", output)
