import json
import random
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent

INPUT_FILE = ROOT / "data" / "final" / "cricket" / "questions.json"
OUTPUT_FILE = ROOT / "data" / "final" / "cricket" / "pilot_sample_100.json"
MANIFEST_FILE = ROOT / "data" / "final" / "cricket" / "pilot_sample_100_manifest.json"

SAMPLE_SIZE = 100
MIN_PER_CATEGORY = 7
RANDOM_SEED = 42


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Questions file not found: {INPUT_FILE}")

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(questions, list):
        raise ValueError("questions.json must contain a JSON list.")

    categories = {}
    for question in questions:
        category = question.get("category") or "uncategorized"
        categories.setdefault(category, []).append(question)

    category_names = sorted(categories)
    if len(category_names) * MIN_PER_CATEGORY > SAMPLE_SIZE:
        raise ValueError(
            f"{len(category_names)} categories need at least "
            f"{len(category_names) * MIN_PER_CATEGORY} places, "
            f"which exceeds sample size {SAMPLE_SIZE}."
        )

    if any(len(items) < MIN_PER_CATEGORY for items in categories.values()):
        too_small = {
            name: len(items)
            for name, items in categories.items()
            if len(items) < MIN_PER_CATEGORY
        }
        raise ValueError(
            "Some categories have fewer than the minimum sample size: "
            f"{too_small}"
        )

    rng = random.Random(RANDOM_SEED)

    # Start with an equal minimum allocation for every category.
    allocation = {
        category: MIN_PER_CATEGORY
        for category in category_names
    }

    remaining = SAMPLE_SIZE - sum(allocation.values())

    # Allocate remaining places proportionally to each category's
    # remaining population, using largest remainders.
    capacities = {
        category: len(categories[category]) - allocation[category]
        for category in category_names
    }
    total_capacity = sum(capacities.values())

    if remaining > total_capacity:
        raise ValueError("Not enough questions to create the requested sample.")

    if remaining:
        exact_shares = {
            category: remaining * capacities[category] / total_capacity
            for category in category_names
        }
        extra = {
            category: min(
                capacities[category],
                int(exact_shares[category])
            )
            for category in category_names
        }

        for category, count in extra.items():
            allocation[category] += count

        places_left = SAMPLE_SIZE - sum(allocation.values())

        remainder_order = sorted(
            category_names,
            key=lambda category: (
                exact_shares[category] - int(exact_shares[category]),
                capacities[category],
                category
            ),
            reverse=True
        )

        while places_left:
            progressed = False
            for category in remainder_order:
                if allocation[category] < len(categories[category]):
                    allocation[category] += 1
                    places_left -= 1
                    progressed = True
                    if places_left == 0:
                        break
            if not progressed:
                raise RuntimeError("Could not complete sample allocation.")

    selected = []
    for category in category_names:
        selected.extend(
            rng.sample(categories[category], allocation[category])
        )

    # Shuffle across categories so the sample is not grouped by category.
    rng.shuffle(selected)

    question_ids = [item.get("question_id") for item in selected]
    if len(selected) != SAMPLE_SIZE or len(set(question_ids)) != SAMPLE_SIZE:
        raise RuntimeError("Sample validation failed: wrong size or duplicate IDs.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(selected, file, indent=2, ensure_ascii=False)

    manifest = {
        "sample_name": "cricket_pilot_sample_100",
        "source_file": str(INPUT_FILE.relative_to(ROOT)),
        "output_file": str(OUTPUT_FILE.relative_to(ROOT)),
        "total_source_questions": len(questions),
        "sample_size": len(selected),
        "sampling_method": "stratified_by_category_with_minimum_allocation",
        "minimum_per_category": MIN_PER_CATEGORY,
        "random_seed": RANDOM_SEED,
        "category_population": {
            category: len(categories[category])
            for category in category_names
        },
        "category_sample_allocation": allocation,
        "actual_category_counts": dict(
            Counter(item.get("category", "uncategorized") for item in selected)
        ),
        "question_ids": question_ids,
    }

    with MANIFEST_FILE.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    print("=" * 65)
    print("HalluBench | Stratified Cricket Pilot Sample")
    print("=" * 65)
    print(f"Source questions: {len(questions):,}")
    print(f"Pilot questions:  {len(selected):,}")
    print(f"Categories:      {len(category_names)}")
    print(f"Random seed:     {RANDOM_SEED}")
    print("\nCategory allocation:")
    for category in category_names:
        print(
            f"  {category:<24} "
            f"{allocation[category]:>3} / {len(categories[category]):>5}"
        )

    print(f"\nSample saved:   {OUTPUT_FILE}")
    print(f"Manifest saved: {MANIFEST_FILE}")
    print("\nOriginal questions.json was not modified.")


if __name__ == "__main__":
    main()
