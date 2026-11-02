import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

FACTS_FILE = BASE_DIR / "data" / "processed" / "cricket" / "facts.json"
PLAYER_MATCH_FILE = BASE_DIR / "data" / "processed" / "cricket" / "player_match_stats.json"
PLAYER_STATS_FILE = BASE_DIR / "data" / "processed" / "cricket" / "player_stats.json"
MATCHES_FILE = BASE_DIR / "data" / "processed" / "cricket" / "matches.json"

OUTPUT_FILE = BASE_DIR / "data" / "final" / "cricket" / "ground_truth.json"

CUTOFF_DATE = "2024-12-31"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_record(
    records,
    domain,
    subject,
    predicate,
    obj,
    match_id=None,
    date=None,
    source_file=None,
    evidence=None,
):
    records.append(
        {
            "ground_truth_id": f"CRICKET-GT-{len(records) + 1:08d}",
            "domain": domain,
            "subject": str(subject) if subject is not None else None,
            "predicate": predicate,
            "object": obj,
            "match_id": str(match_id) if match_id is not None else None,
            "date": date,
            "source_file": source_file,
            "evidence": evidence,
            "verification_status": "source_derived",
            "temporal_cutoff": CUTOFF_DATE,
        }
    )


def main():

    print("=" * 70)
    print("HalluBench - Cricket Ground Truth Builder")
    print("=" * 70)

    facts = load_json(FACTS_FILE)
    player_match_stats = load_json(PLAYER_MATCH_FILE)
    player_stats = load_json(PLAYER_STATS_FILE)
    matches = load_json(MATCHES_FILE)

    ground_truth = []

    # ---------------------------------------------------------
    # 1. Existing source-derived facts
    # ---------------------------------------------------------

    print("\nAdding source-derived facts...")

    for fact in facts:

        add_record(
            ground_truth,
            domain="cricket",
            subject=fact.get("subject"),
            predicate=fact.get("predicate"),
            obj=fact.get("object"),
            match_id=fact.get("match_id"),
            date=fact.get("date"),
            source_file=fact.get("source_file"),
            evidence=fact.get("evidence"),
        )

    print(f"Facts added: {len(ground_truth):,}")

    # ---------------------------------------------------------
    # 2. Player-match statistics
    # ---------------------------------------------------------

    print("\nAdding player-match statistics...")

    player_match_fields = [
        ("runs", "match_runs"),
        ("balls_faced", "match_balls_faced"),
        ("fours", "match_fours"),
        ("sixes", "match_sixes"),
        ("wickets", "match_wickets"),
        ("runs_conceded", "match_runs_conceded"),
        ("balls_bowled", "match_balls_bowled"),
    ]

    for row in player_match_stats:

        player = row.get("player")
        match_id = row.get("match_id")

        for field, predicate in player_match_fields:

            value = row.get(field, 0)

            add_record(
                ground_truth,
                domain="cricket",
                subject=player,
                predicate=predicate,
                obj=value,
                match_id=match_id,
                date=row.get("date"),
                source_file=row.get("source_file"),
                evidence=f"{player} {predicate.replace('_', ' ')}: {value}",
            )

    print(f"After player-match stats: {len(ground_truth):,}")

    # ---------------------------------------------------------
    # 3. Career/player aggregate statistics
    # ---------------------------------------------------------

    print("\nAdding player career statistics...")

    career_fields = [
        ("matches", "career_matches"),
        ("runs", "career_runs"),
        ("balls_faced", "career_balls_faced"),
        ("fours", "career_fours"),
        ("sixes", "career_sixes"),
        ("wickets", "career_wickets"),
        ("runs_conceded", "career_runs_conceded"),
        ("balls_bowled", "career_balls_bowled"),
    ]

    for row in player_stats:

        player = row.get("player")

        for field, predicate in career_fields:

            value = row.get(field, 0)

            add_record(
                ground_truth,
                domain="cricket",
                subject=player,
                predicate=predicate,
                obj=value,
                evidence=f"{player} {predicate.replace('_', ' ')}: {value}",
            )

    print(f"After career stats: {len(ground_truth):,}")

    # ---------------------------------------------------------
    # 4. Match metadata
    # ---------------------------------------------------------

    print("\nAdding match metadata...")

    for match in matches:

        match_id = match.get("match_id")

        if match.get("date"):
            add_record(
                ground_truth,
                "cricket",
                match_id,
                "match_date",
                match.get("date"),
                match_id=match_id,
                date=match.get("date"),
                source_file=match.get("source_file"),
                evidence=f"Match date: {match.get('date')}",
            )

        if match.get("match_type"):
            add_record(
                ground_truth,
                "cricket",
                match_id,
                "match_type",
                match.get("match_type"),
                match_id=match_id,
                date=match.get("date"),
                source_file=match.get("source_file"),
                evidence=f"Match type: {match.get('match_type')}",
            )

        if match.get("winner"):
            add_record(
                ground_truth,
                "cricket",
                match_id,
                "winner",
                match.get("winner"),
                match_id=match_id,
                date=match.get("date"),
                source_file=match.get("source_file"),
                evidence=f"Winner: {match.get('winner')}",
            )

        if match.get("player_of_match"):
            add_record(
                ground_truth,
                "cricket",
                match_id,
                "player_of_match",
                match.get("player_of_match"),
                match_id=match_id,
                date=match.get("date"),
                source_file=match.get("source_file"),
                evidence=f"Player of the match: {match.get('player_of_match')}",
            )

    print(f"After match metadata: {len(ground_truth):,}")

    # ---------------------------------------------------------
    # 5. Save
    # ---------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            ground_truth,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\n" + "=" * 70)
    print("GROUND TRUTH BUILD COMPLETE")
    print("=" * 70)

    print(f"Total ground-truth records: {len(ground_truth):,}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Temporal cutoff: {CUTOFF_DATE}")
    print("=" * 70)


if __name__ == "__main__":
    main()