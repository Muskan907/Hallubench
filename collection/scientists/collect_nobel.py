
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/scientists/nobel_laureates.jsonl"

BASE_URL = "https://api.nobelprize.org/2.1/laureates"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 HalluBench/1.0 (research benchmark)"
}

PER_PAGE = 100
MAX_RETRIES = 3


def fetch_page(offset):
    params = {
        "limit": PER_PAGE,
        "offset": offset
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=90
            )

            if response.status_code == 403:
                print("Nobel API denied access (403).")
                print("Skipping Nobel collection. Other datasets remain usable.")
                return None

            if response.status_code in (429, 500, 502, 503, 504):
                print(
                    f"Temporary error {response.status_code}. "
                    f"Retry {attempt}/{MAX_RETRIES}"
                )
                time.sleep(attempt * 5)
                continue

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            print(f"Request error, attempt {attempt}: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 5)

    print(f"Could not retrieve page at offset {offset}.")
    return None


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    records = []
    seen_ids = set()
    offset = 0

    print("Starting Nobel Prize data collection...")

    while True:
        print(f"Fetching records from offset {offset}...")

        data = fetch_page(offset)

        if data is None:
            break

        laureates = data.get("laureates", [])

        if not laureates:
            break

        for person in laureates:
            laureate_id = person.get("id")

            if not laureate_id or laureate_id in seen_ids:
                continue

            seen_ids.add(laureate_id)

            affiliations = []

            for prize in person.get("nobelPrizes", []):
                for affiliation in prize.get("affiliations", []):
                    name = affiliation.get("name", {}).get("en")
                    if name:
                        affiliations.append(name)

            record = {
                "laureate_id": laureate_id,
                "name": person.get("fullName", {}).get("en"),
                "birth_date": person.get("birth", {}).get("date"),
                "death_date": person.get("death", {}).get("date"),
                "prizes": person.get("nobelPrizes", []),
                "affiliations": sorted(set(affiliations)),
                "source": "Nobel Prize API",
                "source_url": (
                    f"https://www.nobelprize.org/laureate/{laureate_id}"
                )
            }

            records.append(record)

        offset += len(laureates)

        if len(laureates) < PER_PAGE:
            break

        time.sleep(1)

    if not records:
        print("No Nobel records collected. Existing output was not overwritten.")
        return

    with OUTPUT.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("\nNobel collection completed.")
    print(f"Unique laureates: {len(records)}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
