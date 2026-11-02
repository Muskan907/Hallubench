import json
from pathlib import Path
from collections import Counter

INPUT_FILE = Path("data/final/qcommerce/ground_truth.jsonl")
REPORT_FILE = Path("data/final/qcommerce/ground_truth_validation.json")

ALLOWED_ATTRIBUTES = {
    "freshness",
    "food_quality",
    "leakage",
    "packaging_damage",
    "delivery",
    "damaged_product",
    "wrong_or_missing_item",
    "product_performance",
    "appearance_and_size",
    "smell",
    "customer_service",
    "value_for_money"
}


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing file: {INPUT_FILE}")

    total = 0
    errors = []
    warnings = []
    ids = set()
    evidence_counts = Counter()
    attribute_counts = Counter()
    source_counts = Counter()
    verification_counts = Counter()

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue

            total += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({
                    "line": line_number,
                    "problem": f"Invalid JSON: {exc}"
                })
                continue

            record_id = record.get("ground_truth_id")
            source_id = record.get("source_record_id")
            attribute = record.get("attribute")
            evidence = record.get("evidence") or ""
            full_text = record.get("full_review_text") or ""
            title = record.get("review_title") or ""

            if not record_id:
                errors.append({"line": line_number, "problem": "Missing ground_truth_id"})
            elif record_id in ids:
                errors.append({"line": line_number, "problem": f"Duplicate ID: {record_id}"})
            else:
                ids.add(record_id)

            if not source_id:
                errors.append({"line": line_number, "problem": "Missing source_record_id"})

            if attribute not in ALLOWED_ATTRIBUTES:
                errors.append({
                    "line": line_number,
                    "problem": f"Unknown attribute: {attribute}"
                })

            combined_text = f"{title} {full_text}".strip()

            if not evidence:
                errors.append({"line": line_number, "problem": "Missing evidence"})
            elif evidence not in combined_text:
                errors.append({
                    "line": line_number,
                    "problem": "Evidence phrase not found in original title/text",
                    "ground_truth_id": record_id
                })

            if not full_text.strip():
                errors.append({"line": line_number, "problem": "Missing full review text"})

            if record.get("verification_status") != "customer_report_unverified":
                warnings.append({
                    "line": line_number,
                    "problem": "Unexpected verification status"
                })

            evidence_counts[evidence] += 1
            attribute_counts[attribute] += 1
            source_counts[record.get("source_dataset", "unknown")] += 1
            verification_counts[record.get("verification_status", "missing")] += 1

    duplicate_evidence = sum(
        count - 1 for count in evidence_counts.values() if count > 1
    )

    report = {
        "domain": "qcommerce",
        "total_records": total,
        "unique_ground_truth_ids": len(ids),
        "unique_evidence_phrases": len(evidence_counts),
        "repeated_evidence_phrase_occurrences": duplicate_evidence,
        "attribute_counts": dict(attribute_counts),
        "source_counts": dict(source_counts),
        "verification_status_counts": dict(verification_counts),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "validation_status": "PASS" if not errors else "FAIL",
        "errors_sample": errors[:50],
        "warnings_sample": warnings[:20]
    }

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\nQ-COMMERCE GROUND TRUTH VALIDATION")
    print("=" * 48)
    print(f"Records checked: {total}")
    print(f"Unique IDs: {len(ids)}")
    print(f"Unique evidence phrases: {len(evidence_counts)}")
    print(f"Repeated evidence occurrences: {duplicate_evidence}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Status: {report['validation_status']}")

    print("\nSource distribution:")
    for source, count in source_counts.items():
        print(f"{source}: {count}")

    if errors:
        print("\nFirst validation errors:")
        for error in errors[:10]:
            print(error)

    print("\nReport:", REPORT_FILE)


if __name__ == "__main__":
    main()
