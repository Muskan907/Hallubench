
import json
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data/raw/scientists/orcid_ids.txt"
OUTPUT = ROOT / "data/raw/scientists/orcid_records.jsonl"

BASE_URL = "https://pub.orcid.org/v3.0"

session = requests.Session()

retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "HalluBench/1.0"
}


def main():
    if not INPUT.exists():
        print("ORCID input file not found.")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    ids = [
        x.strip()
        for x in INPUT.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]

    completed = set()

    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as f:
            for line in f:
                try:
                    completed.add(json.loads(line)["orcid"])
                except (json.JSONDecodeError, KeyError):
                    continue

    remaining = [x for x in ids if x not in completed]

    print(f"Total ORCID IDs: {len(ids)}")
    print(f"Already collected: {len(completed)}")
    print(f"Remaining: {len(remaining)}")

    success = 0
    failed = 0

    with OUTPUT.open("a", encoding="utf-8") as f:
        for index, orcid in enumerate(remaining, 1):
            url = f"{BASE_URL}/{orcid}/record"

            try:
                response = session.get(
                    url,
                    headers=HEADERS,
                    timeout=(10, 20)
                )

                if response.status_code == 404:
                    failed += 1
                    continue

                response.raise_for_status()

                data = response.json()
                person = data.get("person", {})
                name = person.get("name") or {}

                given = (name.get("given-names") or {}).get("value", "")
                family = (name.get("family-name") or {}).get("value", "")

                record = {
                    "orcid": orcid,
                    "name": f"{given} {family}".strip(),
                    "biography": (
                        person.get("biography") or {}
                    ).get("content"),
                    "record": data,
                    "source": "ORCID",
                    "source_url": f"https://orcid.org/{orcid}"
                }

                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()

                success += 1

            except (requests.RequestException, ValueError) as exc:
                failed += 1
                print(f"Failed {orcid}: {exc}")

            if index % 25 == 0:
                print(
                    f"Progress: {index}/{len(remaining)} | "
                    f"Success: {success} | Failed: {failed}"
                )

            time.sleep(0.5)

    print("\nORCID collection finished.")
    print(f"New records collected: {success}")
    print(f"Failed records: {failed}")
    print(f"Total saved records: {len(completed) + success}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
