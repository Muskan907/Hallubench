import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = BASE_DIR / "data" / "raw" / "cricket" / "odis_json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "cricket" / "matches.json"

CUTOFF_DATE = "2024-12-31"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_date(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def main():

    print("=" * 60)
    print("HalluBench - Cricket Match Parser")
    print("=" * 60)

    files = sorted(RAW_DIR.glob("*.json"))

    print(f"Raw match files found: {len(files):,}")

    records = []

    for index, file_path in enumerate(files, start=1):

        try:
            data = load_json(file_path)
            info = data.get("info", {})

            dates = info.get("dates", [])
            match_date = normalize_date(dates)

            if not match_date:
                continue

            # IMPORTANT:
            # Only retain matches available by the benchmark cutoff.
            if match_date > CUTOFF_DATE:
                continue

            outcome = info.get("outcome", {})

            winner = None

            if isinstance(outcome, dict):
                winner = outcome.get("winner")

            teams = info.get("teams", [])

            record = {
                "match_id": file_path.stem,
                "date": match_date,
                "city": info.get("city"),
                "venue": info.get("venue"),
                "country": info.get("country"),
                "match_type": info.get("match_type"),
                "match_type_number": info.get("match_type_number"),
                "gender": info.get("gender"),
                "teams": teams,
                "winner": winner,
                "player_of_match": info.get("player_of_match", []),
                "players": info.get("players", {}),
                "registry": info.get("registry", {}),
                "event": info.get("event", {})
            }

            records.append(record)

        except Exception as e:

            print(f"ERROR: {file_path.name}: {e}")

        if index % 500 == 0:
            print(f"Processed {index:,}/{len(files):,}")

    records.sort(
        key=lambda x: (x.get("date", ""), x.get("match_id", ""))
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 60)
    print(f"Cutoff: {CUTOFF_DATE}")
    print(f"Matches retained: {len(records):,}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()