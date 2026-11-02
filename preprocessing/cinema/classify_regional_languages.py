import sqlite3
import json
from pathlib import Path
from collections import Counter

DB = Path("data/processed/cinema/cinema.db")
OUT = Path("data/processed/cinema")

conn = sqlite3.connect(DB)
cur = conn.cursor()

languages = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi"
}

print("Analyzing Indian-market title language metadata...")

results = {}

for code, name in languages.items():
    count = cur.execute("""
        SELECT COUNT(DISTINCT a.tconst)
        FROM india_akas a
        JOIN titles t ON a.tconst = t.tconst
        WHERE a.language = ?
    """, (code,)).fetchone()[0]

    results[name] = count
    print(f"{name}: {count:,} titles")

unknown = cur.execute("""
    SELECT COUNT(DISTINCT a.tconst)
    FROM india_akas a
    JOIN titles t ON a.tconst = t.tconst
    WHERE a.language IS NULL
""").fetchone()[0]

print(f"Unknown language: {unknown:,} titles")

total_india = cur.execute("""
    SELECT COUNT(DISTINCT a.tconst)
    FROM india_akas a
    JOIN titles t ON a.tconst = t.tconst
""").fetchone()[0]

summary = {
    "domain": "cinema",
    "classification_basis": "IMDb India-region AKA language metadata",
    "indian_market_titles": total_india,
    "regional_language_counts": results,
    "unknown_language_titles": unknown,
    "warning": "Indian-market releases do not establish Indian film origin. AKA language does not necessarily establish original film language."
}

with open(OUT / "regional_language_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\nTotal Indian-market titles:", f"{total_india:,}")
print("Saved regional_language_summary.json")

conn.close()
