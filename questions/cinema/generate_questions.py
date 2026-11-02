import json
import random
from pathlib import Path
from collections import Counter

GT = Path("data/final/cinema/ground_truth.jsonl")
OUT = Path("data/final/cinema")
OUT.mkdir(parents=True, exist_ok=True)

random.seed(42)

# Balanced sampling quotas
quotas = {
    "title": 5000,
    "release_year": 5000,
    "runtime_minutes": 5000,
    "genres": 5000,
    "average_rating": 5000,
    "num_votes": 5000,
    "directors": 3000,
    "writers": 3000,
    "cast_member": 10000,
    "india_market_alternate_title": 4000
}

samples = {p: [] for p in quotas}
seen = Counter()

print("Scanning ground truth and sampling questions...")

with GT.open("r", encoding="utf-8") as f:
    for line in f:
        g = json.loads(line)
        predicate = g["predicate"]

        if predicate not in quotas:
            continue

        answer = g["object"]
        if answer is None or answer == "":
            continue

        seen[predicate] += 1
        k = quotas[predicate]
        bucket = samples[predicate]

        if len(bucket) < k:
            bucket.append(g)
        else:
            index = random.randrange(seen[predicate])
            if index < k:
                bucket[index] = g

print("\nSampling complete. Generating questions...")

templates = {
    "title": ("movie_information", "What is the title of movie {id}?"),
    "release_year": ("temporal", "In which year was {id} released?"),
    "runtime_minutes": ("numerical", "What is the runtime of {id} in minutes?"),
    "genres": ("movie_information", "What genre information is recorded for {id}?"),
    "average_rating": ("numerical", "What is the IMDb average rating recorded for {id}?"),
    "num_votes": ("numerical", "How many IMDb votes are recorded for {id}?"),
    "directors": ("director_relationship", "Who directed {id} according to IMDb?"),
    "writers": ("writer_relationship", "Who are the writers credited for {id}?"),
    "cast_member": ("cast_relationship", "Which person is credited in the following role for {id}?"),
    "india_market_alternate_title": ("regional_language", "What alternate title is recorded for {id} in the Indian market?")
}

output = OUT / "questions.jsonl"
counts = Counter()
total = 0

with output.open("w", encoding="utf-8") as f:
    for predicate, records in samples.items():
        qtype, template = templates[predicate]

        for g in records:
            answer = g["object"]

            question = template.format(id=g["subject"])

            if predicate == "cast_member":
                question = (
                    f"Which person is credited as {answer['role']} "
                    f"in {g['subject']}?"
                )

            q = {
                "question_id": f"cinema_q_{total + 1:08d}",
                "ground_truth_id": g["ground_truth_id"],
                "domain": "cinema",
                "question_type": qtype,
                "question": question,
                "accepted_answers": [answer],
                "evidence": [g["ground_truth_id"]],
                "answerability": "answerable",
                "subject": g["subject"]
            }

            f.write(json.dumps(q, ensure_ascii=False) + "\n")
            total += 1
            counts[qtype] += 1

summary = {
    "total_questions": total,
    "random_seed": 42,
    "sampling_method": "reservoir_sampling",
    "quotas": quotas,
    "available_records": dict(seen),
    "generated_by_predicate": {
        p: len(records) for p, records in samples.items()
    },
    "question_type_counts": dict(counts)
}

with (OUT / "question_summary.json").open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\nQUESTION GENERATION COMPLETE")
print("Total questions:", total)
print("Question categories:", dict(counts))
print("Output:", output)
print("Summary: data/final/cinema/question_summary.json")
