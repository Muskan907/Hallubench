import json
import random
from pathlib import Path
from collections import Counter, defaultdict

INPUT_FILE = Path("data/final/qcommerce/questions.jsonl")
OUTPUT_FILE = Path("data/final/qcommerce/pilot_sample_100.json")
MANIFEST_FILE = Path("data/final/qcommerce/pilot_sample_100_manifest.json")

SAMPLE_SIZE = 100
SEED = 42


def balanced_attribute_sample(rows, amount, rng):
    """Select questions while spreading selections across attributes."""
    groups = defaultdict(list)

    for row in rows:
        groups[row["attribute"]].append(row)

    for candidates in groups.values():
        rng.shuffle(candidates)

    selected = []
    attributes = sorted(groups)
    rng.shuffle(attributes)

    while len(selected) < amount:
        added = False

        for attribute in attributes:
            if groups[attribute] and len(selected) < amount:
                selected.append(groups[attribute].pop())
                added = True

        if not added:
            break

    return selected


def main():
    rng = random.Random(SEED)

    by_source_type = defaultdict(list)

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            row = json.loads(line)
            key = (row["source_dataset"], row["question_type"])
            by_source_type[key].append(row)

    olist_source = "olist_brazilian_ecommerce"
    amazon_source = "amazon_reviews_2023"

    question_types = [
        "reviewer_report",
        "evidence_retrieval",
        "verification_boundary"
    ]

    selected = []

    # Include all available Olist questions.
    olist_total = 0
    for question_type in question_types:
        candidates = by_source_type[(olist_source, question_type)]
        selected.extend(candidates)
        olist_total += len(candidates)

    if olist_total > SAMPLE_SIZE:
        raise ValueError("Olist questions exceed the requested pilot size.")

    # Fill the remaining sample with Amazon questions.
    amazon_amount = SAMPLE_SIZE - olist_total
    base = amazon_amount // len(question_types)
    remainder = amazon_amount % len(question_types)

    for index, question_type in enumerate(question_types):
        amount = base + (1 if index < remainder else 0)
        candidates = by_source_type[(amazon_source, question_type)]

        if len(candidates) < amount:
            raise ValueError(
                f"Not enough Amazon questions for {question_type}"
            )

        selected.extend(
            balanced_attribute_sample(candidates, amount, rng)
        )

    rng.shuffle(selected)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    source_counts = Counter(q["source_dataset"] for q in selected)
    type_counts = Counter(q["question_type"] for q in selected)
    attribute_counts = Counter(q["attribute"] for q in selected)

    manifest = {
        "domain": "qcommerce",
        "sample_size": len(selected),
        "seed": SEED,
        "sampling_method": (
            "All available Olist questions included; remaining sample "
            "stratified by Amazon question type and balanced across attributes."
        ),
        "source_counts": dict(source_counts),
        "question_type_counts": dict(type_counts),
        "attribute_counts": dict(attribute_counts),
        "limitations": [
            "Olist representation is limited by its small number of "
            "English-keyword-matched reviews.",
            "This is a pilot sample, not a statistically representative "
            "sample of the full review population."
        ]
    }

    with MANIFEST_FILE.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\nBALANCED Q-COMMERCE PILOT CREATED")
    print("=" * 48)
    print("Total questions:", len(selected))
    print("Source distribution:", dict(source_counts))
    print("Question type distribution:", dict(type_counts))
    print("Attributes represented:", len(attribute_counts))
    print("Attribute distribution:", dict(attribute_counts))
    print("Output:", OUTPUT_FILE)
    print("Manifest:", MANIFEST_FILE)


if __name__ == "__main__":
    main()
