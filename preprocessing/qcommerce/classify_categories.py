import json
import re
from pathlib import Path
from collections import Counter

INPUT_FILE = Path("data/processed/qcommerce/combined_reviews.jsonl")
OUTPUT_FILE = Path("data/processed/qcommerce/classified_reviews.jsonl")
SUMMARY_FILE = Path("data/processed/qcommerce/classification_summary.json")

RULES = {
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
    ],
    "positive_experience": [
        r"\bexcellent\b", r"\bamazing\b", r"\bgreat\b",
        r"\bexcellent quality\b", r"\bhighly recommend\b",
        r"\bperfect\b", r"\blove it\b", r"\bvery good\b",
        r"\bsatisfied\b", r"\byummy\b", r"\bdelicious\b"
    ],
    "negative_experience": [
        r"\bpoor quality\b", r"\bdisappointed\b", r"\bterrible\b",
        r"\bawful\b", r"\bworst\b", r"\bnot worth\b",
        r"\bdo not recommend\b", r"\bunsatisfied\b"
    ]
}

COMPILED_RULES = {
    label: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for label, patterns in RULES.items()
}


def classify_review(record):
    text = " ".join([
        str(record.get("title") or ""),
        str(record.get("text") or "")
    ])

    labels = []

    for label, patterns in COMPILED_RULES.items():
        if any(pattern.search(text) for pattern in patterns):
            labels.append(label)

    record["attribute_labels"] = labels or ["unclassified"]
    record["classification_method"] = "keyword_rules_v1"
    record["classification_language"] = "English keyword rules"
    return record


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_FILE}")

    counts = Counter()
    source_counts = Counter()
    total = 0
    multi_label = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            record = json.loads(line)
            record = classify_review(record)

            labels = record["attribute_labels"]
            counts.update(labels)
            source_counts[record.get("source_dataset", "unknown")] += 1

            if len(labels) > 1:
                multi_label += 1

            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1

    summary = {
        "domain": "qcommerce",
        "input_records": total,
        "classified_records": total,
        "multi_label_records": multi_label,
        "classification_method": "transparent keyword rules",
        "classification_note": (
            "Initial English keyword-based labels. These are candidate "
            "attributes, not verified factual claims. Portuguese reviews "
            "are preserved but require a separate multilingual pass."
        ),
        "source_counts": dict(source_counts),
        "attribute_counts": dict(counts)
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\nQ-COMMERCE CLASSIFICATION COMPLETED")
    print("=" * 48)
    print(f"Total records: {total}")
    print(f"Records with multiple labels: {multi_label}")
    print("\nAttribute counts:")

    for label, count in counts.most_common():
        print(f"{label}: {count}")

    print("\nOutput:", OUTPUT_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
