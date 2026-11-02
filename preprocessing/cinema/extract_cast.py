import csv
import gzip
import json
import sqlite3
from pathlib import Path

csv.field_size_limit(2147483647)

RAW = Path("data/raw/cinema")
OUT = Path("data/processed/cinema")
DB = OUT / "cinema.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS cast_members (
    tconst TEXT,
    ordering INTEGER,
    nconst TEXT,
    category TEXT,
    job TEXT,
    characters TEXT
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_cast_tconst ON cast_members(tconst)")
conn.commit()

print("Extracting cast and crew from IMDb principals...")

batch = []
total = 0
matched = 0

with gzip.open(RAW / "title.principals.tsv.gz", "rt",
               encoding="utf-8", newline="") as f:

    reader = csv.DictReader(f, delimiter="\t")

    for r in reader:
        category = r["category"]

        if category not in (
            "actor", "actress", "director", "writer",
            "producer", "cinematographer", "composer",
            "production_designer", "editor"
        ):
            continue

        batch.append((
            r["tconst"],
            int(r["ordering"]),
            r["nconst"],
            category,
            None if r["job"] == r"\N" else r["job"],
            None if r["characters"] == r"\N" else r["characters"]
        ))

        if len(batch) >= 20000:
            cur.executemany(
                "INSERT INTO cast_members VALUES (?,?,?,?,?,?)", batch
            )
            conn.commit()
            total += len(batch)
            batch.clear()

            if total % 200000 == 0:
                print("Processed:", total)

if batch:
    cur.executemany(
        "INSERT INTO cast_members VALUES (?,?,?,?,?,?)", batch
    )
    conn.commit()
    total += len(batch)

matched = cur.execute("""
SELECT COUNT(*)
FROM cast_members c
INNER JOIN titles t ON c.tconst = t.tconst
""").fetchone()[0]

print("\nCAST EXTRACTION COMPLETE")
print("Principal records extracted:", total)
print("Records linked to our movie titles:", matched)

print("\nCategory counts:")
for category, count in cur.execute("""
SELECT category, COUNT(*)
FROM cast_members
GROUP BY category
ORDER BY COUNT(*) DESC
"""):
    print(category, count)

conn.close()
