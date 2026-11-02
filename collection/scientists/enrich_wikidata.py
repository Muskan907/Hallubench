
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/raw/scientists/wikidata_scientists.jsonl"
OUTPUT = ROOT / "data/raw/scientists/wikidata_scientists_enriched.jsonl"

API = "https://www.wikidata.org/w/api.php"
BATCH_SIZE = 50

session = requests.Session()
session.headers.update({
    "User-Agent": "HalluBench/1.0 (scientific research benchmark)"
})


def main():
    with SOURCE.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(records)} Wikidata records")

    enriched = []
    failed = []

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        ids = [r["scientist_id"] for r in batch]

        params = {
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "labels|descriptions",
            "languages": "en",
            "format": "json"
        }

        try:
            response = session.get(API, params=params, timeout=60)
            response.raise_for_status()

            entities = response.json().get("entities", {})

            for record in batch:
                qid = record["scientist_id"]
                entity = entities.get(qid, {})

                record["name"] = (
                    entity.get("labels", {})
                    .get("en", {})
                    .get("value")
                )

                record["description"] = (
                    entity.get("descriptions", {})
                    .get("en", {})
                    .get("value")
                )

                if record["name"]:
                    enriched.append(record)
                else:
                    failed.append(qid)

        except requests.RequestException as exc:
            print(f"Batch failed: {exc}")
            failed.extend(ids)

        print(
            f"Processed {min(start + BATCH_SIZE, len(records))}"
            f"/{len(records)}"
        )

        time.sleep(0.5)

    with OUTPUT.open("w", encoding="utf-8") as f:
        for record in enriched:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("\nWikidata enrichment complete")
    print("Successfully enriched:", len(enriched))
    print("Missing labels:", len(failed))
    print("Output:", OUTPUT)

    if failed:
        print("Unresolved QIDs:", failed)


if __name__ == "__main__":
    main()
