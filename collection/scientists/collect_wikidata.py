import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/scientists/wikidata_scientists.jsonl"

URL = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?person ?birthDate ?deathDate
WHERE {
    ?person wdt:P106 wd:Q901.
    OPTIONAL { ?person wdt:P569 ?birthDate. }
    OPTIONAL { ?person wdt:P570 ?deathDate. }
}
LIMIT 500
"""

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "HalluBench/1.0 (research benchmark)"
    }

    for attempt in range(3):
        try:
            response = requests.get(
                URL,
                params={"query": QUERY},
                headers=headers,
                timeout=180
            )
            response.raise_for_status()
            results = response.json()["results"]["bindings"]
            break
        except requests.RequestException as exc:
            print(f"Attempt {attempt + 1}/3 failed: {exc}")
            if attempt == 2:
                raise
            time.sleep(10)

    records = {}

    for item in results:
        person_url = item["person"]["value"]
        qid = person_url.rsplit("/", 1)[-1]

        records[qid] = {
            "scientist_id": qid,
            "birth_date": item.get("birthDate", {}).get("value"),
            "death_date": item.get("deathDate", {}).get("value"),
            "source": "Wikidata",
            "source_url": person_url
        }

    with OUTPUT.open("w", encoding="utf-8") as f:
        for record in records.values():
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Collected {len(records)} Wikidata records.")
    print(f"Saved: {OUTPUT}")

if __name__ == "__main__":
    main()