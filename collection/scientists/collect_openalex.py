import argparse
import json
import time
from pathlib import Path

import requests
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/scientists/openalex_authors.jsonl"

API_URL = "https://api.openalex.org/authors"

TARGET_COUNT = 1000
PER_PAGE = 200


def collect(dry_run=True):
    print("\nOpenAlex Scientist Collector")
    print("----------------------------")

    if dry_run:
        print("DRY RUN: No API request will be made.")
        print("Source:", API_URL)
        print("Target records:", TARGET_COUNT)
        print("Output:", OUTPUT)
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    records = []
    seen_ids = set()

    pages = (TARGET_COUNT + PER_PAGE - 1) // PER_PAGE

    for page in tqdm(range(1, pages + 1), desc="Collecting authors"):
        params = {
            "filter": "works_count:>0",
            "sort": "cited_by_count:desc",
            "per-page": PER_PAGE,
            "page": page
        }

        response = requests.get(
            API_URL,
            params=params,
            headers={"User-Agent": "HalluBench-Scientists/1.0"},
            timeout=60
        )

        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            break

        for author in results:
            author_id = author.get("id")

            if not author_id or author_id in seen_ids:
                continue

            seen_ids.add(author_id)

            institutions = []

            for institution in author.get("last_known_institutions") or []:
                institutions.append({
                    "id": institution.get("id"),
                    "name": institution.get("display_name"),
                    "country": institution.get("country_code")
                })

            record = {
                "author_id": author_id,
                "name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "works_count": author.get("works_count"),
                "cited_by_count": author.get("cited_by_count"),
                "h_index": author.get("summary_stats", {}).get("h_index"),
                "i10_index": author.get("summary_stats", {}).get("i10_index"),
                "institutions": institutions,
                "source": "OpenAlex",
                "source_url": author_id
            }

            records.append(record)

            if len(records) >= TARGET_COUNT:
                break

        if len(records) >= TARGET_COUNT:
            break

        time.sleep(0.2)

    with OUTPUT.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nCollected {len(records)} unique authors.")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Allow actual OpenAlex API requests."
    )
    args = parser.parse_args()

    collect(dry_run=not args.execute)