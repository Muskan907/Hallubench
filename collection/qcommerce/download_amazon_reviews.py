import json
import time
from pathlib import Path

import requests
from huggingface_hub import hf_hub_url

REPO_ID = "McAuley-Lab/Amazon-Reviews-2023"
OUTPUT_DIR = Path("data/raw/qcommerce/amazon")
MAX_RECORDS = 5000

CATEGORIES = {
    "grocery": "Grocery_and_Gourmet_Food",
    "electronics": "Electronics",
    "mobile_accessories": "Cell_Phones_and_Accessories",
    "beauty_personal_care": "Beauty_and_Personal_Care",
    "home_kitchen": "Home_and_Kitchen",
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def collect_category(label, source_category):
    filename = f"raw/review_categories/{source_category}.jsonl"
    output_file = OUTPUT_DIR / f"{label}_reviews.jsonl"

    if output_file.exists() and output_file.stat().st_size > 0:
        print(f"[SKIP] {label}: output already exists.")
        return

    print(f"\n[START] {label}")
    print(f"Source: {filename}")

    url = hf_hub_url(
        repo_id=REPO_ID,
        filename=filename,
        repo_type="dataset"
    )

    count = 0
    session = requests.Session()

    try:
        with session.get(
            url,
            stream=True,
            timeout=(30, 120)
        ) as response:

            response.raise_for_status()

            with output_file.open("w", encoding="utf-8") as output:
                for line in response.iter_lines(decode_unicode=True):

                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    review_text = record.get("text")

                    if not review_text or not str(review_text).strip():
                        continue

                    cleaned = {
                        "source_dataset": "amazon_reviews_2023",
                        "source_file": filename,
                        "source_category": label,
                        "source_record_id": record.get("review_id"),
                        "product_id": record.get("asin"),
                        "parent_asin": record.get("parent_asin"),
                        "user_id": record.get("user_id"),
                        "rating": record.get("rating"),
                        "title": record.get("title"),
                        "text": review_text,
                        "timestamp": record.get("timestamp"),
                        "helpful_vote": record.get("helpful_vote"),
                        "verified_purchase": record.get("verified_purchase"),
                        "images": record.get("images", [])
                    }

                    output.write(
                        json.dumps(cleaned, ensure_ascii=False) + "\n"
                    )

                    count += 1

                    if count % 500 == 0:
                        print(f"Collected {count}/{MAX_RECORDS}")

                    if count >= MAX_RECORDS:
                        break

        if count == 0:
            output_file.unlink(missing_ok=True)
            print(f"[WARNING] No reviews collected for {label}")
        else:
            print(f"[SUCCESS] {label}: {count} reviews saved")
            print(f"File: {output_file}")

    except Exception as error:
        output_file.unlink(missing_ok=True)
        print(f"[ERROR] {label}: {type(error).__name__}: {error}")

    finally:
        session.close()


def main():
    print("=" * 60)
    print("HALLUBENCH - QUICK COMMERCE DATA COLLECTION")
    print("=" * 60)

    for label, source_category in CATEGORIES.items():
        collect_category(label, source_category)
        time.sleep(2)

    print("\nAmazon collection finished.")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
