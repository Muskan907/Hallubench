import json
import hashlib
from pathlib import Path

import pandas as pd

AMAZON_DIR = Path("data/raw/qcommerce/amazon")
OLIST_DIR = Path("data/raw/qcommerce/olist")
OUTPUT_DIR = Path("data/processed/qcommerce")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AMAZON_FILES = [
    "grocery_reviews.jsonl",
    "electronics_reviews.jsonl",
    "mobile_accessories_reviews.jsonl",
    "beauty_personal_care_reviews.jsonl",
    "home_kitchen_reviews.jsonl",
]


def make_fingerprint(values):
    raw = json.dumps(values, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def clean_amazon():
    print("\nCleaning Amazon reviews...")

    records = []
    seen = set()
    stats = {"read": 0, "kept": 0, "duplicates": 0, "empty": 0}

    for filename in AMAZON_FILES:
        path = AMAZON_DIR / filename

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                stats["read"] += 1
                row = json.loads(line)

                text = str(row.get("text") or "").strip()
                title = str(row.get("title") or "").strip()

                if not text:
                    stats["empty"] += 1
                    continue

                identity = [
                    row.get("source_dataset"),
                    row.get("source_category"),
                    row.get("product_id"),
                    row.get("user_id"),
                    row.get("timestamp"),
                    title,
                    text
                ]

                fingerprint = make_fingerprint(identity)

                if fingerprint in seen:
                    stats["duplicates"] += 1
                    continue

                seen.add(fingerprint)

                row["source_record_id"] = "AMZ-" + fingerprint[:20]
                row["source_record_id_type"] = "sha256_content_fingerprint"
                row["original_source_record_id"] = None
                row["text"] = text
                row["title"] = title
                row["language"] = "undetermined"
                row["cleaning_status"] = "cleaned"

                records.append(row)
                stats["kept"] += 1

    write_jsonl(OUTPUT_DIR / "amazon_cleaned.jsonl", records)

    print(f"Amazon records read: {stats['read']}")
    print(f"Amazon records kept: {stats['kept']}")
    print(f"Duplicates removed: {stats['duplicates']}")
    print(f"Empty reviews removed: {stats['empty']}")

    return records, stats


def clean_olist():
    print("\nCleaning Olist reviews...")

    review_path = OLIST_DIR / "olist_order_reviews_dataset.csv"
    orders_path = OLIST_DIR / "olist_orders_dataset.csv"
    items_path = OLIST_DIR / "olist_order_items_dataset.csv"
    products_path = OLIST_DIR / "olist_products_dataset.csv"
    translation_path = OLIST_DIR / "product_category_name_translation.csv"

    reviews = pd.read_csv(review_path, keep_default_na=False)
    orders = pd.read_csv(orders_path, keep_default_na=False)
    items = pd.read_csv(items_path, keep_default_na=False)
    products = pd.read_csv(products_path, keep_default_na=False)
    translations = pd.read_csv(translation_path, keep_default_na=False)

    category_map = dict(zip(
        translations["product_category_name"],
        translations["product_category_name_english"]
    ))

    product_categories = items.merge(
        products[["product_id", "product_category_name"]],
        on="product_id",
        how="left"
    )

    product_categories["category_english"] = (
        product_categories["product_category_name"]
        .map(category_map)
        .fillna(product_categories["product_category_name"])
    )

    categories_by_order = (
        product_categories.groupby("order_id")["category_english"]
        .apply(lambda values: sorted(set(
            str(v) for v in values if str(v).strip()
        )))
        .to_dict()
    )

    order_dates = orders.set_index("order_id").to_dict("index")

    records = []
    seen = set()
    stats = {"read": len(reviews), "kept": 0, "duplicates": 0, "empty": 0}

    for row in reviews.to_dict("records"):
        title = str(row.get("review_comment_title") or "").strip()
        message = str(row.get("review_comment_message") or "").strip()
        text = " ".join(part for part in [title, message] if part).strip()

        if not text:
            stats["empty"] += 1
            continue

        review_id = str(row.get("review_id") or "").strip()
        order_id = str(row.get("order_id") or "").strip()

        fingerprint = make_fingerprint([
            "olist",
            review_id,
            order_id,
            text
        ])

        if fingerprint in seen:
            stats["duplicates"] += 1
            continue

        seen.add(fingerprint)

        order_info = order_dates.get(order_id, {})

        record = {
            "domain": "qcommerce",
            "source_dataset": "olist_brazilian_ecommerce",
            "source_record_id": review_id or "OLIST-" + fingerprint[:20],
            "source_record_id_type": (
                "dataset_review_id" if review_id
                else "sha256_content_fingerprint"
            ),
            "order_id": order_id,
            "product_categories": categories_by_order.get(order_id, []),
            "rating": row.get("review_score"),
            "title": title,
            "text": text,
            "review_creation_date": row.get("review_creation_date"),
            "review_answer_timestamp": row.get("review_answer_timestamp"),
            "order_status": order_info.get("order_status", ""),
            "order_purchase_timestamp": order_info.get(
                "order_purchase_timestamp", ""
            ),
            "order_delivered_customer_date": order_info.get(
                "order_delivered_customer_date", ""
            ),
            "order_estimated_delivery_date": order_info.get(
                "order_estimated_delivery_date", ""
            ),
            "language": "undetermined",
            "cleaning_status": "cleaned"
        }

        records.append(record)
        stats["kept"] += 1

    write_jsonl(OUTPUT_DIR / "olist_cleaned.jsonl", records)

    print(f"Olist records read: {stats['read']}")
    print(f"Olist records kept: {stats['kept']}")
    print(f"Duplicates removed: {stats['duplicates']}")
    print(f"Empty reviews removed: {stats['empty']}")

    return records, stats


def main():
    amazon_records, amazon_stats = clean_amazon()
    olist_records, olist_stats = clean_olist()

    combined = []

    for row in amazon_records:
        row["domain"] = "qcommerce"
        combined.append(row)

    combined.extend(olist_records)

    write_jsonl(OUTPUT_DIR / "combined_reviews.jsonl", combined)

    manifest = {
        "project": "HalluBench",
        "domain": "qcommerce",
        "sources": {
            "amazon_reviews_2023": amazon_stats,
            "olist_brazilian_ecommerce": olist_stats
        },
        "total_cleaned_records": len(combined),
        "language_detection": "not_performed",
        "deduplication": "source-aware SHA-256 fingerprints",
        "note": "Customer reviews represent reported experiences, not independently verified product defects."
    }

    with (OUTPUT_DIR / "cleaning_manifest.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 55)
    print("Q-COMMERCE CLEANING COMPLETED")
    print("=" * 55)
    print(f"Amazon cleaned: {len(amazon_records)}")
    print(f"Olist cleaned: {len(olist_records)}")
    print(f"Combined records: {len(combined)}")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
