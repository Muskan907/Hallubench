import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data/processed/crm/conversations.jsonl"
OUTPUT_FILE = ROOT / "data/processed/crm/classified_conversations.jsonl"
SUMMARY_FILE = ROOT / "data/processed/crm/classification_summary.json"

PATTERNS = {
    "billing_and_payments": [
        r"\bbill(?:ing)?\b", r"\bcharged\b", r"\bpayment\b",
        r"\bpaid\b", r"\bcredit card\b", r"\bdebit card\b",
        r"\btransaction\b", r"\brefund(?:ed)?\b"
    ],
    "refunds_and_returns": [
        r"\brefund(?:ed)?\b", r"\breturn(?:ed)?\b",
        r"\bexchange\b", r"\bmoney back\b", r"\breimbursement\b"
    ],
    "delivery_and_shipping": [
        r"\bdelivery\b", r"\bdelivered\b", r"\bshipment\b",
        r"\bshipping\b", r"\btracking\b", r"\bpackage\b",
        r"\border\b", r"\bparcel\b", r"\bnot arrived\b",
        r"\blost package\b"
    ],
    "product_or_service_issues": [
        r"\bbroken\b", r"\bdamaged\b", r"\bdefective\b",
        r"\bnot working\b", r"\bpoor quality\b",
        r"\bwrong item\b", r"\bmissing item\b",
        r"\bfaulty\b", r"\bproblem with\b"
    ],
    "account_and_login": [
        r"\blogin\b", r"\blog in\b", r"\bsign in\b",
        r"\bpassword\b", r"\baccount\b", r"\blocked out\b",
        r"\bverification\b", r"\breset password\b"
    ],
    "technical_and_app_issues": [
        r"\bapp\b", r"\bwebsite\b", r"\bcrash(?:ed)?\b",
        r"\berror\b", r"\bbug\b", r"\bnot loading\b",
        r"\bglitch\b", r"\btechnical issue\b"
    ],
    "cancellation": [
        r"\bcancel(?:led|lation)?\b", r"\bterminate\b",
        r"\bstop my subscription\b", r"\bclose my account\b"
    ],
    "booking_and_travel": [
        r"\bflight\b", r"\bairport\b", r"\bbooking\b",
        r"\breservation\b", r"\bseat\b", r"\bboarding\b",
        r"\bhotel\b", r"\btrip\b", r"\btravel\b",
        r"\bcheck.in\b", r"\bdeparture\b"
    ],
    "customer_support": [
        r"\bcustomer service\b", r"\bsupport\b",
        r"\brepresentative\b", r"\bagent\b",
        r"\bno response\b", r"\bnot responding\b",
        r"\bcall(?:ed)? back\b", r"\bprivate message\b",
        r"\bhelp me\b", r"\bassistance\b"
    ],
    "accessibility_assistance": [
        r"\bdisabilit(?:y|ies)\b", r"\bwheelchair\b",
        r"\blegally blind\b", r"\bvisually impaired\b",
        r"\bhearing impaired\b", r"\baccessibility\b",
        r"\bspecial assistance\b", r"\baccessible\b"
    ],
    "positive_feedback": [
        r"\bthank you\b", r"\bthanks\b", r"\bamazing\b",
        r"\bexcellent\b", r"\bgreat service\b",
        r"\bawesome\b", r"\bappreciate\b",
        r"\bwell done\b", r"\bgive .* a raise\b"
    ]
}

COMPILED = {
    category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for category, patterns in PATTERNS.items()
}


def classify_conversation(conversation):
    customer_messages = [
        message for message in conversation.get("messages", [])
        if message.get("direction") == "customer"
    ]

    matched_terms = {}
    combined_text = " ".join(
        message.get("text", "") for message in customer_messages
    )

    for category, patterns in COMPILED.items():
        matches = set()

        for pattern in patterns:
            for match in pattern.finditer(combined_text):
                matches.add(match.group(0).lower())

        if matches:
            matched_terms[category] = sorted(matches)

    categories = sorted(matched_terms.keys())

    if not categories:
        categories = ["other_or_unclassified"]

    conversation["issue_categories"] = categories
    conversation["matched_terms"] = matched_terms
    conversation["classification_method"] = "keyword_based_v1"

    return conversation


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM ISSUE CLASSIFICATION")
    print("=" * 65)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_FILE}")

    category_counts = Counter()
    multi_label_count = 0
    total = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            conversation = json.loads(line)
            conversation = classify_conversation(conversation)

            categories = conversation["issue_categories"]

            category_counts.update(categories)

            if len(categories) > 1:
                multi_label_count += 1

            output.write(
                json.dumps(conversation, ensure_ascii=False) + "\n"
            )

            total += 1

            if total % 50000 == 0:
                print(f"Processed {total:,} conversations...")

    summary = {
        "domain": "crm",
        "source_dataset": "customer_support_on_twitter",
        "classification_method": "keyword_based_v1",
        "total_conversations": total,
        "multi_label_conversations": multi_label_count,
        "single_or_unclassified_conversations": total - multi_label_count,
        "category_counts": dict(category_counts),
        "categories": list(PATTERNS.keys()) + ["other_or_unclassified"],
        "note": (
            "Categories are heuristic labels based on customer message "
            "keywords. They are not independently verified facts."
        )
    }

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("CRM CLASSIFICATION COMPLETED")
    print("=" * 65)
    print(f"Total conversations: {total:,}")
    print(f"Multi-label conversations: {multi_label_count:,}")
    print("\nCategory counts:")

    for category, count in category_counts.most_common():
        print(f"{category}: {count:,}")

    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
