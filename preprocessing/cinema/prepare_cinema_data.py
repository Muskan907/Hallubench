import csv
import gzip
import json
import sqlite3
from pathlib import Path
import sys
csv.field_size_limit(2147483647)

RAW = Path("data/raw/cinema")
OUT = Path("data/processed/cinema")
OUT.mkdir(parents=True, exist_ok=True)

DB = OUT / "cinema.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.executescript("""
DROP TABLE IF EXISTS titles;
DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS crew;
DROP TABLE IF EXISTS india_akas;

CREATE TABLE titles (
    tconst TEXT PRIMARY KEY,
    title_type TEXT,
    primary_title TEXT,
    original_title TEXT,
    start_year TEXT,
    runtime_minutes TEXT,
    genres TEXT
);

CREATE TABLE ratings (
    tconst TEXT PRIMARY KEY,
    average_rating REAL,
    num_votes INTEGER
);

CREATE TABLE crew (
    tconst TEXT PRIMARY KEY,
    directors TEXT,
    writers TEXT
);

CREATE TABLE india_akas (
    tconst TEXT,
    title TEXT,
    language TEXT,
    types TEXT,
    attributes TEXT
);
""")
conn.commit()


def read_tsv(filename):
    path = RAW / filename
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def clean(value):
    return None if value == r"\N" else value


# 1. Movie titles
print("1/4 Loading movie titles...")
batch = []

for r in read_tsv("title.basics.tsv.gz"):
    if r["titleType"] not in ("movie", "tvMovie"):
        continue

    batch.append((
        r["tconst"], r["titleType"], r["primaryTitle"],
        r["originalTitle"], clean(r["startYear"]),
        clean(r["runtimeMinutes"]), clean(r["genres"])
    ))

    if len(batch) >= 10000:
        cur.executemany("INSERT OR IGNORE INTO titles VALUES (?,?,?,?,?,?,?)", batch)
        conn.commit()
        batch.clear()

if batch:
    cur.executemany("INSERT OR IGNORE INTO titles VALUES (?,?,?,?,?,?,?)", batch)
    conn.commit()

print("Titles:", cur.execute("SELECT COUNT(*) FROM titles").fetchone()[0])


# 2. Indian market title and language metadata
print("2/4 Extracting India-region title metadata...")
batch = []

for r in read_tsv("title.akas.tsv.gz"):
    if r["region"] != "IN":
        continue

    batch.append((
        r["titleId"], r["title"], clean(r["language"]),
        clean(r["types"]), clean(r["attributes"])
    ))

    if len(batch) >= 10000:
        cur.executemany("INSERT INTO india_akas VALUES (?,?,?,?,?)", batch)
        conn.commit()
        batch.clear()

if batch:
    cur.executemany("INSERT INTO india_akas VALUES (?,?,?,?,?)", batch)
    conn.commit()

print("India-region title records:", cur.execute(
    "SELECT COUNT(*) FROM india_akas"
).fetchone()[0])


# 3. Ratings
print("3/4 Loading ratings...")
batch = []

for r in read_tsv("title.ratings.tsv.gz"):
    batch.append((
        r["tconst"], float(r["averageRating"]), int(r["numVotes"])
    ))

    if len(batch) >= 10000:
        cur.executemany("INSERT OR REPLACE INTO ratings VALUES (?,?,?)", batch)
        conn.commit()
        batch.clear()

if batch:
    cur.executemany("INSERT OR REPLACE INTO ratings VALUES (?,?,?)", batch)
    conn.commit()


# 4. Directors and writers
print("4/4 Loading directors and writers...")
batch = []

for r in read_tsv("title.crew.tsv.gz"):
    batch.append((
        r["tconst"], clean(r["directors"]), clean(r["writers"])
    ))

    if len(batch) >= 10000:
        cur.executemany("INSERT OR REPLACE INTO crew VALUES (?,?,?)", batch)
        conn.commit()
        batch.clear()

if batch:
    cur.executemany("INSERT OR REPLACE INTO crew VALUES (?,?,?)", batch)
    conn.commit()


# Export combined movie records
print("Exporting processed movie records...")

query = """
SELECT
    t.tconst, t.title_type, t.primary_title, t.original_title,
    t.start_year, t.runtime_minutes, t.genres,
    r.average_rating, r.num_votes,
    c.directors, c.writers
FROM titles t
LEFT JOIN ratings r ON t.tconst = r.tconst
LEFT JOIN crew c ON t.tconst = c.tconst
"""

output = OUT / "movies.jsonl"
count = 0

with output.open("w", encoding="utf-8") as f:
    for row in cur.execute(query):
        record = dict(zip([
            "tconst", "title_type", "primary_title", "original_title",
            "start_year", "runtime_minutes", "genres",
            "average_rating", "num_votes", "directors", "writers"
        ], row))

        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1

print("\nPREPROCESSING COMPLETE")
print("Movie records:", count)
print("Database:", DB)
print("Export:", output)

conn.close()
