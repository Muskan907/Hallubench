import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

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
    / "facts.json"
)


def load_json(path):

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    print("=" * 60)
    print("HalluBench - Cricket Fact Extraction")
    print("=" * 60)

    matches = load_json(MATCHES_FILE)

    facts = []

    for match in matches:

        match_id = match["match_id"]
        date = match.get("date")

        teams = match.get("teams", [])

        # ------------------------------------------------------
        # Match-level facts
        # ------------------------------------------------------

        if date:
            facts.append({
                "subject": match_id,
                "predicate": "match_date",
                "object": date,
                "match_id": match_id,
                "source_file": f"{match_id}.json",
                "evidence": f"Match date: {date}"
            })

        if match.get("match_type"):
            facts.append({
                "subject": match_id,
                "predicate": "match_type",
                "object": match["match_type"],
                "match_id": match_id,
                "source_file": f"{match_id}.json",
                "evidence": f"Match type: {match['match_type']}"
            })

        if match.get("winner"):
            facts.append({
                "subject": match_id,
                "predicate": "winner",
                "object": match["winner"],
                "match_id": match_id,
                "source_file": f"{match_id}.json",
                "evidence": f"Winner: {match['winner']}"
            })

        for team in teams:

            facts.append({
                "subject": team,
                "predicate": "participating_team",
                "object": match_id,
                "match_id": match_id,
                "source_file": f"{match_id}.json",
                "evidence": f"{team} participated in {match_id}"
            })

        # ------------------------------------------------------
        # Player facts
        # ------------------------------------------------------

        players = match.get("players", {})

        for team, player_list in players.items():

            for player in player_list:

                facts.append({
                    "subject": player,
                    "predicate": "played_for",
                    "object": team,
                    "match_id": match_id,
                    "source_file": f"{match_id}.json",
                    "evidence": f"{player} played for {team}"
                })

                facts.append({
                    "subject": player,
                    "predicate": "played_in",
                    "object": match_id,
                    "match_id": match_id,
                    "source_file": f"{match_id}.json",
                    "evidence": f"{player} played in {match_id}"
                })

        # ------------------------------------------------------
        # Player of match
        # ------------------------------------------------------

        for player in match.get("player_of_match", []):

            facts.append({
                "subject": player,
                "predicate": "player_of_match",
                "object": match_id,
                "match_id": match_id,
                "source_file": f"{match_id}.json",
                "evidence": f"{player} was Player of the Match"
            })

    print(f"Matches processed: {len(matches):,}")
    print(f"Facts generated: {len(facts):,}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            facts,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()