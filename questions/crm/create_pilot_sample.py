import json
import random
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[2]

GT_FILE = ROOT / "data/final/crm/ground_truth.jsonl"
QUESTIONS_FILE = ROOT / "data/final/crm/questions.jsonl"

OUTPUT_FILE = ROOT / "data/final/crm/pilot_sample_100.json"
MANIFEST_FILE = ROOT / "data/final/crm/pilot_sample_100_manifest.json"

SEED = 42
SAMPLE_SIZE = 100

TYPE_QUOTAS = {
    "customer_report": 34,
    "evidence_retrieval": 33,
    "company_response_context": 33
}


def reservoir_sample(records, quota, rng):
    """Reservoir sample a fixed number of records."""
    reservoir = []
    count = 0

    for record in records:
        count += 1

        if len(reservoir) < quota:
            reservoir.append(record)
        else:
            index = rng.randrange(count)
            if index < quota:
                reservoir[index] = record

    if count < quota:
        raise ValueError(
            f"Only {count} records available, but {quota} required."
        )

    return reservoir, count


def main():
    rng = random.Random(SEED)

    print("=" * 65)
    print("HALLUBENCH | CRM PILOT SAMPLE GENERATION")
    print("=" * 65)

    if not GT_FILE.exists() or not QUESTIONS_FILE.exists():
        raise FileNotFoundError("Ground truth or questions file missing.")

    # First pass: discover CRM attributes.
    attributes = set()

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                gt = json.loads(line)
                attributes.add(gt["attribute"])

    attributes = sorted(attributes)

    if not attributes:
        raise ValueError("No CRM attributes found.")

    # Allocate approximately equal samples to each attribute.
    base = SAMPLE_SIZE // len(attributes)
    remainder = SAMPLE_SIZE % len(attributes)

    extra_attributes = set(rng.sample(attributes, remainder))

    attribute_quotas = {
        attribute: base + (1 if attribute in extra_attributes else 0)
        for attribute in attributes
    }

    print("\nAttribute quotas:")
    for attribute, quota in attribute_quotas.items():
        print(f"{attribute}: {quota}")

    # Second pass: sample unique ground-truth records by attribute.
    reservoirs = {attribute: [] for attribute in attributes}
    counts = Counter()

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            gt = json.loads(line)
            attribute = gt["attribute"]

            counts[attribute] += 1
            quota = attribute_quotas[attribute]
            reservoir = reservoirs[attribute]
            count = counts[attribute]

            if len(reservoir) < quota:
                reservoir.append(gt)
            else:
                index = rng.randrange(count)
                if index < quota:
                    reservoir[index] = gt

    selected_gt = []

    for attribute, quota in attribute_quotas.items():
        if len(reservoirs[attribute]) != quota:
            raise ValueError(
                f"Insufficient ground truth for {attribute}"
            )

        selected_gt.extend(reservoirs[attribute])

    if len(selected_gt) != SAMPLE_SIZE:
        raise RuntimeError("Incorrect number of sampled ground-truth records.")

    selected_ids = {
        gt["ground_truth_id"] for gt in selected_gt
    }

    if len(selected_ids) != SAMPLE_SIZE:
        raise RuntimeError("Duplicate ground-truth records selected.")

    # Assign one question type to each selected ground-truth record.
    assignments = []

    for question_type, quota in TYPE_QUOTAS.items():
        assignments.extend([question_type] * quota)

    rng.shuffle(assignments)
    rng.shuffle(selected_gt)

    assigned_types = {
        gt["ground_truth_id"]: question_type
        for gt, question_type in zip(selected_gt, assignments)
    }

    # Third pass: retrieve only the assigned questions.
    selected_questions = {}

    with QUESTIONS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            question = json.loads(line)
            gt_id = question.get("ground_truth_id")

            if gt_id not in assigned_types:
                continue

            if question.get("question_type") != assigned_types[gt_id]:
                continue

            selected_questions[gt_id] = question

            if len(selected_questions) == SAMPLE_SIZE:
                break

    missing = selected_ids - set(selected_questions)

    if missing:
        raise RuntimeError(
            f"Could not find questions for {len(missing)} selected records."
        )

    pilot = list(selected_questions.values())
    rng.shuffle(pilot)

    type_counts = Counter(
        q["question_type"] for q in pilot
    )

    attribute_counts = Counter(
        q["attribute"] for q in pilot
    )

    response_status = Counter(
        "response_present" if q.get("context", {}).get("company_messages")
        else "no_company_response"
        for q in pilot
        if q["question_type"] == "company_response_context"
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(pilot, f, indent=2, ensure_ascii=False)

    manifest = {
        "domain": "crm",
        "sample_size": len(pilot),
        "random_seed": SEED,
        "sampling_method": (
            "Stratified reservoir sampling by attribute, "
            "with one question per unique ground-truth record."
        ),
        "question_type_counts": dict(type_counts),
        "attribute_counts": dict(attribute_counts),
        "company_response_status": dict(response_status),
        "unique_ground_truth_records": len(selected_ids),
        "unique_question_ids": len({
            q["question_id"] for q in pilot
        }),
        "source_dataset": "customer_support_on_twitter",
        "note": (
            "Balanced pilot sample for pipeline testing. "
            "It is not a statistically representative estimate "
            "of the complete CRM dataset."
        )
    }

    with MANIFEST_FILE.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("CRM PILOT SAMPLE GENERATED")
    print("=" * 65)
    print(f"Total questions: {len(pilot)}")
    print(f"Unique ground-truth records: {len(selected_ids)}")
    print(f"Unique question IDs: {len({q['question_id'] for q in pilot})}")

    print("\nQuestion type distribution:")
    for name, count in type_counts.items():
        print(f"{name}: {count}")

    print("\nAttribute distribution:")
    for name, count in attribute_counts.items():
        print(f"{name}: {count}")

    print("\nCompany response status:")
    for name, count in response_status.items():
        print(f"{name}: {count}")

    print(f"\nPilot: {OUTPUT_FILE}")
    print(f"Manifest: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
