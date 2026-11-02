import csv
import gzip
import sqlite3
from pathlib import Path

csv.field_size_limit(2147483647)

RAW = Path("data/raw/cinema")
DB = Path("data/processed/cinema/cinema.db")

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS people (
    nconst TEXT PRIMARY KEY,
    name TEXT,
    birth_year TEXT,
    death_year TEXT,
    professions TEXT,
    known_for TEXT
)
""")
conn.commit()

print("Extracting IMDb person names...")
batch = []
total = 0

with gzip.open(RAW / "name.basics.tsv.gz", "rt",
               encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for r in reader:
        batch.append((
            r["nconst"],
            r["primaryName"],
            None if r["birthYear"] == r"\N" else r["birthYear"],
            None if r["deathYear"] == r"\N" else r["deathYear"],
            None if r["primaryProfession"] == r"\N" else r["primaryProfession"],
            None if r["knownForTitles"] == r"\N" else r["knownForTitles"]
        ))

        if len(batch) >= 20000:
            cur.executemany(
                "INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?)", batch
            )
            conn.commit()
            total += len(batch)
            batch.clear()

if batch:
    cur.executemany(
        "INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?)", batch
    )
    conn.commit()
    total += len(batch)

print("People loaded:", total)

print("\nSample linked cast:")
for row in cur.execute("""
SELECT t.primary_title, p.name, c.category, c.characters
FROM cast_members c
JOIN titles t ON c.tconst = t.tconst
JOIN people p ON c.nconst = p.nconst
LIMIT 10
"""):
    print(row)

conn.close()
