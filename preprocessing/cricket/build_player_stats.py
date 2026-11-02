import json
from pathlib import Path
from collections import defaultdict


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cricket"
    / "player_match_stats.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cricket"
    / "player_stats.json"
)


def load_json(path):

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    print("=" * 60)
    print("HalluBench - Cricket Player Statistics")
    print("=" * 60)

    records = load_json(INPUT_FILE)

    players = defaultdict(
        lambda: {
            "matches": 0,
            "runs": 0,
            "balls_faced": 0,
            "fours": 0,
            "sixes": 0,
            "wickets": 0,
            "runs_conceded": 0,
            "balls_bowled": 0
        }
    )

    for record in records:

        player = record["player"]

        players[player]["matches"] += 1

        for field in [
            "runs",
            "balls_faced",
            "fours",
            "sixes",
            "wickets",
            "runs_conceded",
            "balls_bowled"
        ]:
            players[player][field] += record.get(field, 0)

    results = []

    for player, stats in players.items():

        results.append({
            "player": player,
            **stats
        })

    results.sort(
        key=lambda x: x["runs"],
        reverse=True
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(f"Players: {len(results):,}")
    print(f"Saved to: {OUTPUT_FILE}")

    print()
    print("Top 10 by runs:")

    for i, player in enumerate(results[:10], start=1):

        print(
            f"{i}. {player['player']} - "
            f"{player['runs']} runs"
        )


if __name__ == "__main__":
    main()