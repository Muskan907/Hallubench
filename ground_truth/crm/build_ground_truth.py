import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data/processed/crm/attribute_evidence.jsonl"
OUTPUT_FILE = ROOT / "data/final/crm/ground_truth.jsonl"
SUMMARY_FILE = ROOT / "data/final/crm/ground_truth_summary.json"


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM GROUND TRUTH GENERATION")
    print("=" * 65)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    category_counts = Counter()
    source_counts = Counter()
    seen_ids = set()
    errors = []

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue

            evidence = json.loads(line)

            evidence_id = evidence.get("evidence_id")
            conversation_id = evidence.get("conversation_id")
            attribute = evidence.get("attribute")
            customer_evidence = evidence.get("evidence", [])

            if not evidence_id or not conversation_id or not attribute:
                errors.append({
                    "line": line_number,
                    "reason": "Missing evidence ID, conversation ID, or attribute"
                })
                continue

            if not customer_evidence:
                errors.append({
                    "line": line_number,
                    "reason": "No customer evidence"
                })
                continue

            if evidence_id in seen_ids:
                errors.append({
                    "line": line_number,
                    "reason": "Duplicate evidence ID"
                })
                continue

            seen_ids.add(evidence_id)

            record = {
                "ground_truth_id": evidence_id,
                "domain": "crm",
                "subject": conversation_id,
                "predicate": attribute,
                "object": [
                    item.get("text", "")
                    for item in customer_evidence
                ],
                "attribute": attribute,
                "claim_type": "customer_reported_experience",
                "conversation_id": conversation_id,
                "customer_evidence": customer_evidence,
                "company_responses": evidence.get("company_responses", []),
                "source_dataset": evidence.get("source_dataset"),
                "source_record_id": conversation_id,
                "source_record_id_type": "conversation_id",
                "conversation_message_count": evidence.get(
                    "conversation_message_count"
                ),
                "verification_status": "customer_report_unverified",
                "evidence_status": "keyword_matched_customer_message",
                "extraction_method": evidence.get("extraction_method"),
                "temporal_cutoff": None
            }

            output.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

            total += 1
            category_counts[attribute] += 1
            source_counts[record["source_dataset"]] += 1

            if total % 50000 == 0:
                print(f"Generated {total:,} ground-truth records...")

    summary = {
        "domain": "crm",
        "source_dataset": "customer_support_on_twitter",
        "total_ground_truth_records": total,
        "unique_ground_truth_ids": len(seen_ids),
        "category_counts": dict(category_counts),
        "source_counts": dict(source_counts),
        "error_count": len(errors),
        "errors": errors[:100],
        "verification_status": "customer_report_unverified",
        "method": "evidence_based_keyword_extraction",
        "note": (
            "Records represent customer-reported experiences. "
            "They do not establish independent objective verification "
            "or confirmed issue resolution."
        )
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("CRM GROUND TRUTH GENERATION COMPLETED")
    print("=" * 65)
    print(f"Total records: {total:,}")
    print(f"Unique IDs: {len(seen_ids):,}")
    print(f"Errors: {len(errors):,}")

    print("\nCategory counts:")
    for category, count in category_counts.most_common():
        print(f"{category}: {count:,}")

    print(f"\nGround truth: {OUTPUT_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
