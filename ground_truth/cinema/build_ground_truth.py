import sqlite3
import json
from pathlib import Path

DB = Path("data/processed/cinema/cinema.db")
OUT = Path("data/final/cinema")
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)

movie_cur = conn.cursor()
cast_cur = conn.cursor()
aka_cur = conn.cursor()

languages = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali",
    "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi"
}

output = OUT / "ground_truth.jsonl"
count = 0
counts = {"movie_facts": 0, "cast_facts": 0, "aka_facts": 0}

def write_fact(f, subject, predicate, obj):
    global count

    if obj is None or obj == "":
        return

    record = {
        "ground_truth_id": f"cinema_{subject}_{predicate}_{count}",
        "domain": "cinema",
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source_dataset": "IMDb",
        "source_record_id": subject
    }

    f.write(json.dumps(record, ensure_ascii=False) + "\n")
    count += 1

print("Building cinema ground truth...")

with output.open("w", encoding="utf-8") as f:

    # 1. Basic movie facts
    print("1/3 Extracting movie facts...")

    movie_cur.execute("""
        SELECT t.tconst, t.primary_title, t.original_title,
               t.title_type, t.start_year, t.runtime_minutes,
               t.genres, r.average_rating, r.num_votes,
               c.directors, c.writers
        FROM titles t
        LEFT JOIN ratings r ON t.tconst = r.tconst
        LEFT JOIN crew c ON t.tconst = c.tconst
    """)

    while True:
        rows = movie_cur.fetchmany(5000)
        if not rows:
            break

        for row in rows:
            mid = row[0]

            predicates = [
                "title", "original_title", "title_type",
                "release_year", "runtime_minutes", "genres",
                "average_rating", "num_votes", "directors", "writers"
            ]

            for predicate, obj in zip(predicates, row[1:]):
                write_fact(f, mid, predicate, obj)
                if obj is not None and obj != "":
                    counts["movie_facts"] += 1

    print("Movie facts:", counts["movie_facts"])

    # 2. Cast and crew relationships
    print("2/3 Extracting cast and crew facts...")

    cast_cur.execute("""
        SELECT c.tconst, p.name, c.category, c.characters
        FROM cast_members c
        JOIN titles t ON c.tconst = t.tconst
        JOIN people p ON c.nconst = p.nconst
        ORDER BY c.tconst
    """)

    while True:
        rows = cast_cur.fetchmany(5000)
        if not rows:
            break

        for mid, name, category, characters in rows:
            write_fact(f, mid, "cast_member", {
                "name": name,
                "role": category,
                "characters": characters
            })
            counts["cast_facts"] += 1

        if count % 500000 == 0:
            print("Facts generated:", count)

    print("Cast facts:", counts["cast_facts"])

    # 3. Indian-market alternate titles
    print("3/3 Extracting Indian-market metadata...")

    aka_cur.execute("""
        SELECT a.tconst, a.title, a.language, a.types, a.attributes
        FROM india_akas a
        JOIN titles t ON a.tconst = t.tconst
    """)

    while True:
        rows = aka_cur.fetchmany(5000)
        if not rows:
            break

        for mid, title, language, types, attributes in rows:
            write_fact(f, mid, "india_market_alternate_title", {
                "title": title,
                "language_code": language,
                "language_name": languages.get(
                    language, "Other/Unknown"
                ),
                "types": types,
                "attributes": attributes,
                "region": "IN"
            })
            counts["aka_facts"] += 1

print("\nGROUND TRUTH BUILD COMPLETE")
print("Movie facts:", counts["movie_facts"])
print("Cast facts:", counts["cast_facts"])
print("AKA facts:", counts["aka_facts"])
print("TOTAL FACTS:", count)
print("Output:", output)

with open(OUT / "ground_truth_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "total_facts": count,
        "counts": counts,
        "movie_count": 916452,
        "source": "IMDb datasets"
    }, f, indent=2)

conn.close()
