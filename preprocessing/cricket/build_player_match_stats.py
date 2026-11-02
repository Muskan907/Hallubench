import json
from pathlib import Path
from collections import defaultdict


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = (
    BASE_DIR
    / "data"
    / "raw"
    / "cricket"
    / "odis_json"
)

MATCHES_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cricket"
    / "matches.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cricket"
    / "player_match_stats.json"
)

CUTOFF_DATE = "2024-12-31"


# ============================================================
# WICKET TYPES CREDITED TO THE BOWLER
# ============================================================

BOWLER_WICKET_KINDS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket",
}


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("HalluBench - Cricket Player-Match Statistics")
    print("=" * 70)

    print(f"Temporal cutoff: {CUTOFF_DATE}")
    print()

    matches = load_json(MATCHES_FILE)

    results = []

    processed_matches = 0
    skipped_matches = 0

    # ========================================================
    # PROCESS EACH MATCH
    # ========================================================

    for index, match in enumerate(matches, start=1):

        match_id = str(match["match_id"])

        raw_file = RAW_DIR / f"{match_id}.json"

        if not raw_file.exists():
            skipped_matches += 1
            continue

        data = load_json(raw_file)

        info = data.get("info", {})

        # ----------------------------------------------------
        # Match date
        # ----------------------------------------------------

        dates = info.get("dates", [])

        if dates:
            date = str(dates[0])
        else:
            date = None

        # ----------------------------------------------------
        # Extra safety cutoff
        # ----------------------------------------------------

        if date and date > CUTOFF_DATE:
            skipped_matches += 1
            continue

        # ----------------------------------------------------
        # Player statistics container
        # ----------------------------------------------------

        stats = defaultdict(
            lambda: {
                "runs": 0,
                "balls_faced": 0,
                "fours": 0,
                "sixes": 0,
                "wickets": 0,
                "runs_conceded": 0,
                "balls_bowled": 0,
            }
        )

        # ====================================================
        # PROCESS INNINGS
        # ====================================================

        for innings in data.get("innings", []):

            for over in innings.get("overs", []):

                for delivery in over.get("deliveries", []):

                    batter = delivery.get("batter")
                    bowler = delivery.get("bowler")

                    runs = delivery.get("runs", {})

                    batter_runs = runs.get("batter", 0)
                    total_runs = runs.get("total", 0)

                    extras = delivery.get("extras", {})

                    # ==================================================
                    # BATTING
                    # ==================================================

                    if batter:

                        # Runs scored by batter
                        stats[batter]["runs"] += batter_runs

                        # A wide is not a ball faced.
                        if "wides" not in extras:
                            stats[batter]["balls_faced"] += 1

                        # Boundary counts
                        if batter_runs == 4:
                            stats[batter]["fours"] += 1

                        if batter_runs == 6:
                            stats[batter]["sixes"] += 1

                    # ==================================================
                    # BOWLING
                    # ==================================================

                    if bowler:

                        # ----------------------------------------------
                        # Runs conceded by bowler
                        #
                        # Byes, leg-byes and penalty runs are not
                        # charged to the bowler.
                        # Wides and no-balls ARE charged to the bowler.
                        # ----------------------------------------------

                        bowler_runs = (
                            total_runs
                            - extras.get("byes", 0)
                            - extras.get("legbyes", 0)
                            - extras.get("penalty", 0)
                        )

                        stats[bowler]["runs_conceded"] += bowler_runs

                        # ----------------------------------------------
                        # Legal delivery
                        #
                        # Wides and no-balls are not legal balls.
                        # ----------------------------------------------

                        if (
                            "wides" not in extras
                            and "noballs" not in extras
                        ):
                            stats[bowler]["balls_bowled"] += 1

                    # ==================================================
                    # WICKETS
                    # ==================================================

                    for wicket in delivery.get("wickets", []):

                        kind = wicket.get("kind")

                        # ----------------------------------------------
                        # ONLY count wickets credited to the bowler.
                        #
                        # Run outs, retired hurt, retired out and
                        # obstructing the field are NOT bowler wickets.
                        # ----------------------------------------------

                        if (
                            bowler
                            and kind in BOWLER_WICKET_KINDS
                        ):
                            stats[bowler]["wickets"] += 1

        # ========================================================
        # PLAYERS IN MATCH
        # ========================================================

        players = info.get("players", {})

        all_players = set()

        for player_list in players.values():

            for player in player_list:
                all_players.add(player)

        # ========================================================
        # CREATE PLAYER-MATCH RECORDS
        # ========================================================

        for player in sorted(all_players):

            s = stats[player]

            results.append(
                {
                    "player": player,
                    "match_id": match_id,
                    "date": date,
                    "teams": info.get("teams", []),

                    # Batting
                    "runs": s["runs"],
                    "balls_faced": s["balls_faced"],
                    "fours": s["fours"],
                    "sixes": s["sixes"],

                    # Bowling
                    "wickets": s["wickets"],
                    "runs_conceded": s["runs_conceded"],
                    "balls_bowled": s["balls_bowled"],
                }
            )

        processed_matches += 1

        # ====================================================
        # PROGRESS
        # ====================================================

        if index % 250 == 0:

            print(
                f"Processed {index:,}/{len(matches):,} "
                f"| Player-match records: {len(results):,}"
            )

    # ============================================================
    # SAVE OUTPUT
    # ============================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    print()
    print("=" * 70)
    print("PLAYER-MATCH STATISTICS COMPLETE")
    print("=" * 70)

    print(f"Input matches:          {len(matches):,}")
    print(f"Matches processed:      {processed_matches:,}")
    print(f"Matches skipped:        {skipped_matches:,}")
    print(f"Player-match records:   {len(results):,}")
    print(f"Temporal cutoff:        {CUTOFF_DATE}")
    print(f"Output:                 {OUTPUT_FILE}")

    print("=" * 70)


if __name__ == "__main__":
    main()