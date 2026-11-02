import json
import re
from pathlib import Path
from collections import Counter

INPUT_FILE = Path("data/processed/qcommerce/classified_reviews.jsonl")
OUTPUT_FILE = Path("data/processed/qcommerce/attribute_evidence.jsonl")
SUMMARY_FILE = Path("data/processed/qcommerce/attribute_evidence_summary.json")

# Sentiment labels are retained in the review but are not product attributes.
NON_ATTRIBUTE_LABELS = {
    "positive_experience",
    "negative_experience",
    "unclassified"
}

PATTERNS = {
    "freshness": [
        r"\bfresh\b", r"\bstale\b", r"\bspoiled?\b", r"\brotten\b",
        r"\bexpired\b", r"\bexpiry\b", r"\bperishab\w*\b"
    ],
    "food_quality": [
        r"\btaste\b", r"\btasteless\b", r"\bflavou?r\b", r"\byummy\b",
        r"\bdelicious\b", r"\bbland\b", r"\bsour\b", r"\bfood quality\b"
    ],
    "leakage": [
        r"\bleak\w*\b", r"\bspill\w*\b", r"\bseep\w*\b",
        r"\bliquid came out\b"
    ],
    "packaging_damage": [
        r"\bpackag\w*\b", r"\bbox was damaged\b", r"\btorn\b",
        r"\bbroken seal\b", r"\bopen package\b", r"\bcrushed\b",
        r"\bdented\b", r"\bscratch\w*\b"
    ],
    "delivery": [
        r"\bdeliver\w*\b", r"\bshipping\b", r"\bshipment\b",
        r"\blate\b", r"\bdelayed\b", r"\bearly\b", r"\bon time\b",
        r"\btracking\b"
    ],
    "damaged_product": [
        r"\bdamaged\b", r"\bbroken\b", r"\bcracked\b",
        r"\bdefect\w*\b", r"\bnot working\b", r"\bdoes not work\b"
    ],
    "wrong_or_missing_item": [
        r"\bwrong item\b", r"\bwrong product\b", r"\bmissing item\b",
        r"\bnot received\b", r"\bnever received\b", r"\bincorrect item\b"
    ],
    "product_performance": [
        r"\bperformance\b", r"\bworks well\b", r"\bworks great\b",
        r"\bstopped working\b", r"\bbattery\b", r"\bcharging\b",
        r"\bconnectivity\b", r"\bslow\b", r"\bfast\b"
    ],
    "appearance_and_size": [
        r"\bcolour\b", r"\bcolor\b", r"\bappearance\b",
        r"\bsize\b", r"\bfit\b", r"\blooks like\b",
        r"\bas pictured\b", r"\bnot as shown\b"
    ],
    "smell": [
        r"\bsmell\b", r"\bsmelly\b", r"\bodou?r\b",
        r"\bfragrance\b", r"\bstink\b"
    ],
    "customer_service": [
        r"\bcustomer service\b", r"\bsupport\b", r"\brefund\b",
        r"\breplacement\b", r"\breturn\b", r"\bcomplaint\b",
        r"\bresponse\b"
    ],
    "value_for_money": [
        r"\bprice\b", r"\bvalue for money\b", r"\bexpensive\b",
        r"\boverpriced\b", r"\bworth it\b", r"\bcheap\b"
    ]
}

COMPILED = {
    label: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for label, patterns in PATTERNS.items()
}


def extract_evidence(text, patterns):
    matches = []

    for pattern in patterns:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 70)
            end = min(len(text), match.end() + 70)

            evidence = text[start:end].strip()

            if evidence and evidence not in matches:
                matches.append(evidence)

    return matches


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    attribute_counts = Counter()
    source_counts = Counter()
    total_reviews = 0
    reviews_with_evidence = 0
    total_attribute_entries = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            record = json.loads(line)
            total_reviews += 1

            text = " ".join([
                str(record.get("title") or ""),
                str(record.get("text") or "")
            ]).strip()

            extracted = []

            for label in record.get("attribute_labels", []):
                if label in NON_ATTRIBUTE_LABELS:
                    continue

                evidence = extract_evidence(text, COMPILED.get(label, []))

                if evidence:
                    extracted.append({
                        "attribute": label,
                        "evidence_phrases": evidence
                    })
                    attribute_counts[label] += 1

            if extracted:
                reviews_with_evidence += 1
                total_attribute_entries += len(extracted)

                result = {
                    "domain": "qcommerce",
                    "source_dataset": record.get("source_dataset"),
                    "source_record_id": record.get("source_record_id"),
                    "source_record_id_type": record.get("source_record_id_type"),
                    "product_id": record.get("product_id"),
                    "parent_asin": record.get("parent_asin"),
                    "order_id": record.get("order_id"),
                    "source_category": record.get("source_category"),
                    "product_categories": record.get("product_categories", []),
                    "rating": record.get("rating"),
                    "title": record.get("title"),
                    "text": record.get("text"),
                    "attributes": extracted,
                    "evidence_status": "review_text_matched",
                    "verification_status": "customer_report_unverified"
                }

                output.write(json.dumps(result, ensure_ascii=False) + "\n")

                source_counts[record.get("source_dataset", "unknown")] += 1

    summary = {
        "domain": "qcommerce",
        "input_reviews": total_reviews,
        "reviews_with_attribute_evidence": reviews_with_evidence,
        "total_attribute_entries": total_attribute_entries,
        "attribute_counts": dict(attribute_counts),
        "source_counts": dict(source_counts),
        "verification_status": "customer_report_unverified",
        "note": (
            "Evidence phrases are extracted from customer review text. "
            "They represent customer-reported experiences and are not "
            "independent verification of product defects or delivery events."
        )
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\nATTRIBUTE EVIDENCE EXTRACTION COMPLETED")
    print("=" * 48)
    print(f"Reviews processed: {total_reviews}")
    print(f"Reviews with attribute evidence: {reviews_with_evidence}")
    print(f"Total attribute entries: {total_attribute_entries}")
    print("\nAttribute counts:")

    for label, count in attribute_counts.most_common():
        print(f"{label}: {count}")

    print("\nOutput:", OUTPUT_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
