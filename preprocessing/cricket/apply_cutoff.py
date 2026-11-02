import json
from pathlib import Path
from datetime import date


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cricket"
    / "matches.json"
)

CUTOFF = date(2024, 12, 31)


def main():

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        matches = json.load(f)

    violations = []

    for match in matches:

        match_date = date.fromisoformat(match["date"])

        if match_date > CUTOFF:
            violations.append(
                (match["match_id"], match["date"])
            )

    print("=" * 60)
    print("HalluBench - Temporal Cutoff Audit")
    print("=" * 60)

    print(f"Total matches: {len(matches):,}")
    print(f"Cutoff: {CUTOFF}")
    print(f"Violations: {len(violations):,}")

    if violations:

        print("\nERROR: cutoff violations found.")

        for item in violations[:10]:
            print(item)

    else:

        print("\nPASS: No post-cutoff matches found.")


if __name__ == "__main__":
    main()