import json
import hashlib
from pathlib import Path
from collections import Counter

INPUT_FILE = Path("data/final/qcommerce/ground_truth.jsonl")
OUTPUT_FILE = Path("data/final/qcommerce/questions.jsonl")
SUMMARY_FILE = Path("data/final/qcommerce/question_summary.json")

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

ATTRIBUTE_NAMES = {
    "freshness": "freshness",
    "food_quality": "food quality",
    "leakage": "leakage",
    "packaging_damage": "packaging or packaging damage",
    "delivery": "delivery",
    "damaged_product": "product damage",
    "wrong_or_missing_item": "a wrong or missing item",
    "product_performance": "product performance",
    "appearance_and_size": "appearance or size",
    "smell": "smell or odour",
    "customer_service": "customer service",
    "value_for_money": "price or value for money"
}


def make_question_id(ground_truth_id, question_type):
    raw = f"{ground_truth_id}|{question_type}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "QCQ-" + digest[:20]


def build_questions(record):
    attribute = record["attribute"]
    attribute_name = ATTRIBUTE_NAMES.get(attribute, attribute.replace("_", " "))
    evidence = record["evidence"]

    questions = [
        {
            "question_type": "reviewer_report",
            "question": (
                f"What experience does the customer report about "
                f"{attribute_name} in this review?"
            ),
            "expected_answer": (
                f"The customer reports: {evidence}"
            ),
            "accepted_answers": [evidence],
            "answer_policy": "Must reflect the customer's reported experience."
        },
        {
            "question_type": "evidence_retrieval",
            "question": (
                f"Identify the exact phrase in the review that supports "
                f"the reported experience related to {attribute_name}."
            ),
            "expected_answer": evidence,
            "accepted_answers": [evidence],
            "answer_policy": "Return the source-supported evidence phrase."
        },
        {
            "question_type": "verification_boundary",
            "question": (
                f"Does this customer review independently establish that "
                f"the product or delivery objectively had a {attribute_name} "
                f"defect, or does it only document the customer's report?"
            ),
            "expected_answer": (
                "It only documents the customer's reported experience. "
                "The review alone does not independently verify an "
                "objective product or delivery defect."
            ),
            "accepted_answers": [
                "It only documents the customer's reported experience.",
                "The review does not independently verify an objective defect."
            ],
            "answer_policy": (
                "Do not treat a customer report as independent verification."
            )
        }
    ]

    results = []

    for item in questions:
        question_type = item["question_type"]

        results.append({
            "question_id": make_question_id(
                record["ground_truth_id"], question_type
            ),
            "domain": "qcommerce",
            "question_type": question_type,
            "question": item["question"],
            "expected_answer": item["expected_answer"],
            "accepted_answers": item["accepted_answers"],
            "answer_policy": item["answer_policy"],

            # Ground-truth reference
            "ground_truth_id": record["ground_truth_id"],
            "attribute": attribute,

            # Kept for evaluation, not sent separately to the model
            "evidence": evidence,

            # Original context supplied to the model
            "review_title": record.get("review_title", ""),
            "review_context": record.get("full_review_text", ""),

            # Source provenance
            "source_dataset": record.get("source_dataset"),
            "source_record_id": record.get("source_record_id"),
            "verification_status": record.get("verification_status"),

            "question_generation_method": "deterministic_evidence_templates"
        })

    return results


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    question_counts = Counter()
    source_counts = Counter()
    attribute_counts = Counter()
    seen_ids = set()

    ground_truth_count = 0
    total_questions = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            record = json.loads(line)
            ground_truth_count += 1

            for question in build_questions(record):
                question_id = question["question_id"]

                if question_id in seen_ids:
                    raise ValueError(f"Duplicate question ID: {question_id}")

                seen_ids.add(question_id)

                output.write(
                    json.dumps(question, ensure_ascii=False) + "\n"
                )

                question_counts[question["question_type"]] += 1
                source_counts[question["source_dataset"] or "unknown"] += 1
                attribute_counts[question["attribute"]] += 1
                total_questions += 1

    summary = {
        "domain": "qcommerce",
        "ground_truth_records": ground_truth_count,
        "total_questions": total_questions,
        "unique_question_ids": len(seen_ids),
        "questions_per_ground_truth_record": 3,
        "question_type_counts": dict(question_counts),
        "source_question_counts": dict(source_counts),
        "attribute_question_counts": dict(attribute_counts),
        "generation_method": "deterministic evidence-based templates",
        "limitations": [
            "Questions are generated from customer-reported review evidence.",
            "Verification-boundary questions test evidence limitations.",
            "This version does not generate false-premise questions.",
            "Question templates require further quality review."
        ]
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\nQ-COMMERCE QUESTION GENERATION COMPLETED")
    print("=" * 52)
    print(f"Ground truth records: {ground_truth_count}")
    print(f"Questions generated: {total_questions}")
    print(f"Unique question IDs: {len(seen_ids)}")

    print("\nQuestion type counts:")
    for name, count in question_counts.items():
        print(f"{name}: {count}")

    print("\nSource distribution:")
    for name, count in source_counts.items():
        print(f"{name}: {count}")

    print("\nOutput:", OUTPUT_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
