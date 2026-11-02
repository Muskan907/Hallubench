import json
from pathlib import Path
from collections import Counter

import pandas as pd

AMAZON_DIR = Path("data/raw/qcommerce/amazon")
OLIST_DIR = Path("data/raw/qcommerce/olist")

AMAZON_FILES = [
    "grocery_reviews.jsonl",
    "electronics_reviews.jsonl",
    "mobile_accessories_reviews.jsonl",
    "beauty_personal_care_reviews.jsonl",
    "home_kitchen_reviews.jsonl",
]


def audit_amazon():
    print("\n" + "=" * 65)
    print("AMAZON REVIEWS DATA AUDIT")
    print("=" * 65)

    total = 0

    for filename in AMAZON_FILES:
        path = AMAZON_DIR / filename

        if not path.exists():
            print(f"[MISSING] {filename}")
            continue

        count = 0
        ratings = Counter()
        unique_ids = set()
        missing_text = 0
        first_record = {}

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                record = json.loads(line)
                count += 1

                ratings[str(record.get("rating"))] += 1

                review_id = record.get("source_record_id")
                if review_id:
                    unique_ids.add(review_id)

                if not record.get("text"):
                    missing_text += 1

                if count == 1:
                    first_record = record

        total += count

        print(f"\nCategory: {filename}")
        print(f"Records: {count}")
        print(f"Unique source IDs: {len(unique_ids)}")
        print(f"Missing review text: {missing_text}")
        print(f"Rating distribution: {dict(ratings)}")
        print("Sample review:")
        print(str(first_record.get("text", ""))[:300])

    print(f"\nTOTAL AMAZON REVIEWS: {total}")


def audit_olist():
    print("\n" + "=" * 65)
    print("OLIST DATA AUDIT")
    print("=" * 65)

    files = [
        "olist_order_reviews_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_products_dataset.csv",
        "product_category_name_translation.csv",
    ]

    for filename in files:
        path = OLIST_DIR / filename

        if not path.exists():
            print(f"[MISSING] {filename}")
            continue

        df = pd.read_csv(path)

        print(f"\nFile: {filename}")
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print(f"Duplicate rows: {df.duplicated().sum()}")
        print(f"Missing values:\n{df.isnull().sum().to_string()}")

        if filename == "olist_order_reviews_dataset.csv":
            print("\nReview score distribution:")
            print(df["review_score"].value_counts(dropna=False).sort_index())

            print("\nSample review comments:")
            print(
                df[["review_score", "review_comment_title",
                    "review_comment_message"]]
                .head(5)
                .to_string(index=False)
            )

        if filename == "olist_products_dataset.csv":
            print("\nProduct category distribution:")
            print(df["product_category_name"].value_counts().head(15))


def main():
    audit_amazon()
    audit_olist()

    print("\n" + "=" * 65)
    print("DATA AUDIT COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()
