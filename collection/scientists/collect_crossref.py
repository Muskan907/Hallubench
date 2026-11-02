import json
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/scientists/crossref_publications.jsonl"

URL = "https://api.crossref.org/works"

TERMS = [
    "artificial intelligence",
    "machine learning",
    "physics",
    "chemistry",
    "biology",
    "mathematics",
    "medicine",
    "astronomy",
    "neuroscience",
    "climate science"
]

PER_TERM = 100

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    count = 0

    with OUTPUT.open("w", encoding="utf-8") as f:
        for term in TERMS:
            params = {
                "query": term,
                "rows": PER_TERM,
                "select": "DOI,title,author,published,created,type,publisher"
            }

            try:
                response = requests.get(
                    URL,
                    params=params,
                    headers={"User-Agent": "HalluBench/1.0 (scientists benchmark)"},
                    timeout=60
                )
                response.raise_for_status()

                items = response.json()["message"]["items"]

                for item in items:
                    doi = item.get("DOI")
                    if not doi or doi in seen:
                        continue
                    seen.add(doi)

                    record = {
                        "doi": doi,
                        "title": item.get("title", [None])[0],
                        "authors": [
                            {
                                "given": a.get("given"),
                                "family": a.get("family"),
                                "orcid": a.get("ORCID")
                            }
                            for a in item.get("author", [])
                        ],
                        "published": item.get("published", {}).get("date-parts"),
                        "type": item.get("type"),
                        "publisher": item.get("publisher"),
                        "source": "Crossref",
                        "source_url": f"https://doi.org/{doi}"
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

                print(f"{term}: processed {len(items)} records")
                time.sleep(0.5)

            except requests.RequestException as exc:
                print(f"Crossref error for {term}: {exc}")

    print(f"\nSaved {count} unique publications to {OUTPUT}")

if __name__ == "__main__":
    main()