import json
import hashlib
from pathlib import Path
from collections import Counter

INPUT_FILE = Path("data/processed/qcommerce/attribute_evidence.jsonl")
OUTPUT_FILE = Path("data/final/qcommerce/ground_truth.jsonl")
SUMMARY_FILE = Path("data/final/qcommerce/ground_truth_summary.json")

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def make_id(source_id, attribute, evidence):
    raw = f"{source_id}|{attribute}|{evidence}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "QC-" + digest[:20]


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    counts = Counter()
    source_counts = Counter()
    verification_counts = Counter()
    seen = set()

    input_reviews = 0
    total_records = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            review = json.loads(line)
            input_reviews += 1

            source_id = review.get("source_record_id")
            source_name = review.get("source_dataset")

            for attribute_data in review.get("attributes", []):
                attribute = attribute_data.get("attribute")

                for evidence in attribute_data.get("evidence_phrases", []):
                    ground_truth_id = make_id(
                        source_id,
                        attribute,
                        evidence
                    )

                    if ground_truth_id in seen:
                        continue

                    seen.add(ground_truth_id)

                    record = {
                        "ground_truth_id": ground_truth_id,
                        "domain": "qcommerce",
                        "attribute": attribute,
                        "claim_type": "customer_reported_experience",
                        "claim": (
                            f"A customer review reports an experience "
                            f"related to {attribute.replace('_', ' ')}."
                        ),
                        "evidence": evidence,
                        "full_review_text": review.get("text", ""),
                        "review_title": review.get("title", ""),
                        "source_dataset": source_name,
                        "source_record_id": source_id,
                        "source_record_id_type": review.get(
                            "source_record_id_type"
                        ),
                        "product_id": review.get("product_id"),
                        "parent_asin": review.get("parent_asin"),
                        "order_id": review.get("order_id"),
                        "source_category": review.get("source_category"),
                        "product_categories": review.get(
                            "product_categories", []
                        ),
                        "rating": review.get("rating"),
                        "verification_status": "customer_report_unverified",
                        "evidence_status": "review_text_matched",
                        "temporal_cutoff": None
                    }

                    output.write(
                        json.dumps(record, ensure_ascii=False) + "\n"
                    )

                    counts[attribute] += 1
                    source_counts[source_name or "unknown"] += 1
                    verification_counts[
                        record["verification_status"]
                    ] += 1
                    total_records += 1

    summary = {
        "domain": "qcommerce",
        "input_reviews_with_evidence": input_reviews,
        "ground_truth_records": total_records,
        "unique_ground_truth_ids": len(seen),
        "attribute_counts": dict(counts),
        "source_counts": dict(source_counts),
        "verification_status_counts": dict(verification_counts),
        "ground_truth_policy": (
            "Records represent customer-reported experiences supported "
            "by review text. They are not independently verified claims "
            "about objective product quality or delivery performance."
        ),
        "limitations": [
            "Initial attribute matching uses English keyword rules.",
            "Olist Portuguese reviews have limited attribute coverage.",
            "Keyword matches require further quality review.",
            "Amazon and Olist are general e-commerce sources, not direct "
            "quick-commerce platform datasets."
        ]
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\nQ-COMMERCE GROUND TRUTH BUILD COMPLETED")
    print("=" * 52)
    print(f"Input reviews: {input_reviews}")
    print(f"Ground truth records: {total_records}")
    print(f"Unique IDs: {len(seen)}")

    print("\nAttribute counts:")
    for attribute, count in counts.most_common():
        print(f"{attribute}: {count}")

    print("\nSource counts:")
    for source_name, count in source_counts.items():
        print(f"{source_name}: {count}")

    print("\nOutput:", OUTPUT_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
