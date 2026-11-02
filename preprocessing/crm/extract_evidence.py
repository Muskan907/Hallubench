import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data/processed/crm/classified_conversations.jsonl"
OUTPUT_FILE = ROOT / "data/processed/crm/attribute_evidence.jsonl"
SUMMARY_FILE = ROOT / "data/processed/crm/attribute_evidence_summary.json"

EXCLUDED = {"other_or_unclassified"}


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM ATTRIBUTE EVIDENCE EXTRACTION")
    print("=" * 65)

    counts = Counter()
    total_records = 0
    conversations_with_evidence = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            conversation = json.loads(line)
            messages = conversation.get("messages", [])

            customer_messages = [
                m for m in messages
                if m.get("direction") == "customer"
            ]

            company_messages = [
                m for m in messages
                if m.get("direction") == "company"
            ]

            categories = [
                c for c in conversation.get("issue_categories", [])
                if c not in EXCLUDED
            ]

            conversation_had_evidence = False

            for category in categories:
                terms = conversation.get("matched_terms", {}).get(category, [])

                # Keep customer messages containing an extracted keyword.
                evidence_messages = []

                for message in customer_messages:
                    text = message.get("text", "")
                    text_lower = text.lower()

                    matched = [
                        term for term in terms
                        if term.lower() in text_lower
                    ]

                    if matched:
                        evidence_messages.append({
                            "message_id": message.get("message_id"),
                            "created_at_utc": message.get("created_at_utc"),
                            "text": text,
                            "matched_terms": matched
                        })

                # Do not create evidence records without matching messages.
                if not evidence_messages:
                    continue

                record = {
                    "evidence_id": (
                        f"crm_{conversation['conversation_id']}_{category}"
                    ),
                    "domain": "crm",
                    "conversation_id": conversation["conversation_id"],
                    "source_dataset": conversation.get("source_dataset"),
                    "attribute": category,
                    "claim_type": "customer_reported_experience",
                    "evidence": evidence_messages,
                    "company_responses": [
                        {
                            "message_id": m.get("message_id"),
                            "created_at_utc": m.get("created_at_utc"),
                            "text": m.get("text")
                        }
                        for m in company_messages
                    ],
                    "conversation_message_count": len(messages),
                    "verification_status": "customer_report_unverified",
                    "evidence_status": "keyword_matched_customer_message",
                    "extraction_method": "keyword_based_v1"
                }

                output.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

                counts[category] += 1
                total_records += 1
                conversation_had_evidence = True

            if conversation_had_evidence:
                conversations_with_evidence += 1

            if conversations_with_evidence % 50000 == 0 and conversation_had_evidence:
                print(
                    f"Evidence extracted from "
                    f"{conversations_with_evidence:,} conversations..."
                )

    summary = {
        "domain": "crm",
        "source_dataset": "customer_support_on_twitter",
        "total_evidence_records": total_records,
        "conversations_with_evidence": conversations_with_evidence,
        "category_counts": dict(counts),
        "verification_status": "customer_report_unverified",
        "method": "keyword_based_v1",
        "note": (
            "Extracted customer messages are evidence of reported experiences, "
            "not independent verification of the reported issue. Company "
            "responses are retained as conversation context."
        )
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("CRM EVIDENCE EXTRACTION COMPLETED")
    print("=" * 65)
    print(f"Conversations with evidence: {conversations_with_evidence:,}")
    print(f"Total evidence records: {total_records:,}")

    for category, count in counts.most_common():
        print(f"{category}: {count:,}")

    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
