import json
import random
from pathlib import Path
from collections import Counter, defaultdict

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

GROUND_TRUTH_FILE = BASE_DIR / "data" / "final" / "cricket" / "ground_truth.json"
PLAYER_STATS_FILE = BASE_DIR / "data" / "processed" / "cricket" / "player_stats.json"
PLAYER_MATCH_FILE = BASE_DIR / "data" / "processed" / "cricket" / "player_match_stats.json"
MATCHES_FILE = BASE_DIR / "data" / "processed" / "cricket" / "matches.json"
OUTPUT_FILE = BASE_DIR / "data" / "final" / "cricket" / "questions.json"

CUTOFF_DATE = "2024-12-31"
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# These are upper targets. The generator never fabricates source-backed
# ground truth just to reach a target. It uses as many valid source-backed
# records as are available.
TARGETS = {
    "numerical": 2500,
    "match_statistic": 2500,
    "temporal": 1500,
    "relationship": 1500,
    "multi_entity": 1500,
    "multi_hop": 1500,
    "comparison": 1500,
    "false_premise": 1500,
    "unsupported_claim": 1500,
    "fabricated_entity": 1000,
    "proper_noun": 1000,
    "alias_nickname": 500,
    "attribute": 1000,
    "ambiguous": 1000,
    "uniqueness": 500,
    "adversarial_numerical": 1000,
}

# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_question(
    questions,
    question,
    expected_answer,
    question_type,
    hallucination_target,
    category,
    ground_truth_ids=None,
    evaluation_policy="exact_or_normalized",
    difficulty="medium",
    metadata=None,
):
    questions.append({
        "question_id": "",
        "domain": "cricket",
        "question": question,
        "question_type": question_type,
        "category": category,
        "expected_answer": expected_answer,
        "hallucination_target": hallucination_target,
        "evaluation_policy": evaluation_policy,
        "difficulty": difficulty,
        "ground_truth_ids": ground_truth_ids or [],
        "temporal_cutoff": CUTOFF_DATE,
        "metadata": metadata or {},
    })


def count_category(questions, category):
    return sum(q["category"] == category for q in questions)


def safe_object(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def make_unique_question(questions, seen, **kwargs):
    key = (
        kwargs["question"],
        kwargs["category"],
        kwargs["hallucination_target"],
    )
    if key in seen:
        return False
    seen.add(key)
    add_question(questions, **kwargs)
    return True


def aliases_for_player(player):
    # These are benchmark probes, not claims that the aliases are
    # officially recorded by the Cricsheet source.
    known = {
        "MS Dhoni": ["Mahi", "Captain Cool", "MSD", "Dhoni"],
        "Sachin Tendulkar": ["Little Master", "Master Blaster", "Sachin"],
        "Virat Kohli": ["King Kohli", "Virat", "Cheeku"],
        "Rohit Sharma": ["Hitman", "Rohit", "Sharma"],
        "AB de Villiers": ["Mr. 360", "ABD", "AB"],
    }
    return known.get(player, [])


def synthetic_name(i):
    first = [
        "Aarav", "Arjun", "Kabir", "Rohan", "Vihaan",
        "Aditya", "Karan", "Rahul", "Aman", "Dev",
    ]
    last = [
        "Thunder", "Storm", "Boundary", "Wicket",
        "Six", "Yorker", "Cover", "Swing", "Bat",
        "Cricket",
    ]
    return f"{first[i % len(first)]} {last[i % len(last)]}{i + 1}"


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 75)
    print("HalluBench - Cricket Question Generator")
    print("=" * 75)

    ground_truth = load_json(GROUND_TRUTH_FILE)
    player_stats = load_json(PLAYER_STATS_FILE)
    player_match_stats = load_json(PLAYER_MATCH_FILE)
    matches = load_json(MATCHES_FILE)

    print(f"Ground-truth records: {len(ground_truth):,}")
    print(f"Players: {len(player_stats):,}")
    print(f"Player-match records: {len(player_match_stats):,}")
    print(f"Matches: {len(matches):,}")

    # --------------------------------------------------------
    # INDEX SOURCE-BACKED GROUND TRUTH
    # --------------------------------------------------------

    career = {}
    match_stats = {}
    dates = {}
    winners = {}
    player_of_match = {}
    predicate_records = defaultdict(list)

    for gt in ground_truth:
        subject = gt.get("subject")
        predicate = gt.get("predicate")
        match_id = gt.get("match_id")

        predicate_records[predicate].append(gt)

        if predicate.startswith("career_"):
            career[(subject, predicate)] = gt

        elif predicate.startswith("match_"):
            match_stats[(subject, predicate, match_id)] = gt

        elif predicate == "match_date":
            dates[match_id] = gt

        elif predicate == "winner":
            winners[match_id] = gt

        elif predicate == "player_of_match":
            player_of_match[match_id] = gt

    players = [
        p.get("player")
        for p in player_stats
        if p.get("player")
    ]
    players = list(dict.fromkeys(players))
    random.shuffle(players)

    player_match_rows = list(player_match_stats)
    random.shuffle(player_match_rows)

    questions = []
    seen = set()

    # ========================================================
    # 1. CAREER NUMERICAL
    # ========================================================

    print("[1/16] Career numerical...")

    numerical_templates = [
        ("career_runs", "How many ODI runs has {player} scored?"),
        ("career_matches", "How many ODI matches has {player} played?"),
        ("career_balls_faced", "How many ODI balls has {player} faced?"),
        ("career_fours", "How many fours has {player} scored in ODIs?"),
        ("career_sixes", "How many sixes has {player} scored in ODIs?"),
        ("career_wickets", "How many ODI wickets has {player} taken?"),
        ("career_balls_bowled", "How many balls has {player} bowled in ODIs?"),
    ]

    for player in players:
        if count_category(questions, "numerical") >= TARGETS["numerical"]:
            break

        for predicate, template in numerical_templates:
            gt = career.get((player, predicate))
            if not gt:
                continue

            make_unique_question(
                questions, seen,
                question=template.format(player=player),
                expected_answer=gt["object"],
                question_type="factual",
                hallucination_target="numerical_error",
                category="numerical",
                ground_truth_ids=[gt["ground_truth_id"]],
                evaluation_policy="numeric_exact",
                difficulty="easy",
                metadata={"entity": player, "predicate": predicate},
            )

            if count_category(questions, "numerical") >= TARGETS["numerical"]:
                break

    # ========================================================
    # 2. MATCH STATISTICS
    # ========================================================

    print("[2/16] Match statistics...")

    match_templates = [
        ("match_runs", "How many runs did {player} score in ODI match {match_id}?"),
        ("match_balls_faced", "How many balls did {player} face in ODI match {match_id}?"),
        ("match_fours", "How many fours did {player} hit in ODI match {match_id}?"),
        ("match_sixes", "How many sixes did {player} hit in ODI match {match_id}?"),
        ("match_wickets", "How many wickets did {player} take in ODI match {match_id}?"),
    ]

    for row in player_match_rows:
        if count_category(questions, "match_statistic") >= TARGETS["match_statistic"]:
            break

        player = row.get("player")
        match_id = row.get("match_id")

        for predicate, template in match_templates:
            gt = match_stats.get((player, predicate, match_id))
            if not gt:
                continue

            make_unique_question(
                questions, seen,
                question=template.format(player=player, match_id=match_id),
                expected_answer=gt["object"],
                question_type="factual",
                hallucination_target="numerical_error",
                category="match_statistic",
                ground_truth_ids=[gt["ground_truth_id"]],
                evaluation_policy="numeric_exact",
                difficulty="medium",
                metadata={
                    "entity": player,
                    "match_id": match_id,
                    "predicate": predicate,
                },
            )

            if count_category(questions, "match_statistic") >= TARGETS["match_statistic"]:
                break

    # ========================================================
    # 3. TEMPORAL
    # ========================================================

    print("[3/16] Temporal...")

    date_records = list(dates.values())
    random.shuffle(date_records)

    for gt in date_records:
        if count_category(questions, "temporal") >= TARGETS["temporal"]:
            break

        make_unique_question(
            questions, seen,
            question=f"When was ODI match {gt['match_id']} played?",
            expected_answer=gt["object"],
            question_type="factual",
            hallucination_target="temporal_error",
            category="temporal",
            ground_truth_ids=[gt["ground_truth_id"]],
            evaluation_policy="date_normalized",
            difficulty="easy",
            metadata={"match_id": gt["match_id"]},
        )

    # ========================================================
    # 4. RELATIONSHIP
    # ========================================================

    print("[4/16] Relationship...")

    winner_records = list(winners.values())
    random.shuffle(winner_records)

    relationship_templates = [
        "Which team won ODI match {match_id}?",
        "What was the winning team in ODI match {match_id}?",
        "Which side won ODI {match_id}?",
    ]

    for gt in winner_records:
        if count_category(questions, "relationship") >= TARGETS["relationship"]:
            break

        template = random.choice(relationship_templates)

        make_unique_question(
            questions, seen,
            question=template.format(match_id=gt["match_id"]),
            expected_answer=gt["object"],
            question_type="factual",
            hallucination_target="relationship_error",
            category="relationship",
            ground_truth_ids=[gt["ground_truth_id"]],
            evaluation_policy="entity_normalized",
            difficulty="easy",
            metadata={
                "relation": "winner",
                "match_id": gt["match_id"],
            },
        )

    # ========================================================
    # 5. PROPER NOUN / PLAYER OF MATCH
    # ========================================================

    print("[5/16] Proper-noun/entity questions...")

    pom_records = list(player_of_match.values())
    random.shuffle(pom_records)

    pom_templates = [
        "Who was the Player of the Match in ODI {match_id}?",
        "Which player was named Player of the Match in ODI {match_id}?",
        "Who received the Player of the Match award in ODI {match_id}?",
    ]

    for gt in pom_records:
        if count_category(questions, "proper_noun") >= TARGETS["proper_noun"]:
            break

        expected = gt["object"]

        make_unique_question(
            questions, seen,
            question=random.choice(pom_templates).format(match_id=gt["match_id"]),
            expected_answer=expected,
            question_type="entity",
            hallucination_target="wrong_entity",
            category="proper_noun",
            ground_truth_ids=[gt["ground_truth_id"]],
            evaluation_policy="entity_normalized",
            difficulty="medium",
            metadata={"match_id": gt["match_id"]},
        )

    # ========================================================
    # 6. MULTI ENTITY
    # ========================================================

    print("[6/16] Multi-entity...")

    player_run_records = []

    for player in players:
        gt = career.get((player, "career_runs"))
        if gt:
            player_run_records.append((player, gt))

    random.shuffle(player_run_records)

    multi_templates = [
        "How many ODI runs has {p1} scored, and how many has {p2} scored?",
        "Give the ODI run totals for {p1} and {p2}.",
        "Compare the ODI run totals of {p1} and {p2}.",
    ]

    for i in range(0, len(player_run_records) - 1, 2):
        if count_category(questions, "multi_entity") >= TARGETS["multi_entity"]:
            break

        p1, gt1 = player_run_records[i]
        p2, gt2 = player_run_records[i + 1]

        make_unique_question(
            questions, seen,
            question=random.choice(multi_templates).format(p1=p1, p2=p2),
            expected_answer={
                p1: gt1["object"],
                p2: gt2["object"],
            },
            question_type="multi_entity",
            hallucination_target="entity_mixing",
            category="multi_entity",
            ground_truth_ids=[
                gt1["ground_truth_id"],
                gt2["ground_truth_id"],
            ],
            evaluation_policy="multi_entity_numeric",
            difficulty="hard",
            metadata={"entities": [p1, p2]},
        )

    # ========================================================
    # 7. MULTI HOP
    # ========================================================

    print("[7/16] Multi-hop...")

    multi_hop_templates = [
        "Which team won ODI match {match_id}, and on what date was it played?",
        "For ODI {match_id}, give the winning team and match date.",
        "What was the winner of ODI {match_id} and when was the match played?",
    ]

    for match_id, winner_gt in winners.items():
        if count_category(questions, "multi_hop") >= TARGETS["multi_hop"]:
            break

        date_gt = dates.get(match_id)
        if not date_gt:
            continue

        winner = safe_object(winner_gt["object"])
        date = date_gt["object"]

        make_unique_question(
            questions, seen,
            question=random.choice(multi_hop_templates).format(match_id=match_id),
            expected_answer={
                "winner": winner,
                "date": date,
            },
            question_type="multi_hop",
            hallucination_target="multi_hop_error",
            category="multi_hop",
            ground_truth_ids=[
                winner_gt["ground_truth_id"],
                date_gt["ground_truth_id"],
            ],
            evaluation_policy="multi_claim",
            difficulty="hard",
            metadata={"match_id": match_id, "hop_count": 2},
        )

    # ========================================================
    # 8. COMPARISON
    # ========================================================

    print("[8/16] Comparison...")

    comparison_templates = [
        "Who has scored more ODI runs, {p1} or {p2}?",
        "Which player has the higher ODI run total, {p1} or {p2}?",
        "Between {p1} and {p2}, who has more ODI runs?",
    ]

    for i in range(0, len(player_run_records) - 1, 2):
        if count_category(questions, "comparison") >= TARGETS["comparison"]:
            break

        p1, gt1 = player_run_records[i]
        p2, gt2 = player_run_records[i + 1]

        v1 = gt1["object"]
        v2 = gt2["object"]

        if v1 > v2:
            expected = p1
        elif v2 > v1:
            expected = p2
        else:
            expected = "Tie"

        make_unique_question(
            questions, seen,
            question=random.choice(comparison_templates).format(p1=p1, p2=p2),
            expected_answer=expected,
            question_type="comparison",
            hallucination_target="comparison_error",
            category="comparison",
            ground_truth_ids=[
                gt1["ground_truth_id"],
                gt2["ground_truth_id"],
            ],
            evaluation_policy="comparison",
            difficulty="medium",
            metadata={
                "entities": [p1, p2],
                "values": [v1, v2],
            },
        )

    # ========================================================
    # 9. ADVERSARIAL NUMERICAL
    # ========================================================

    print("[9/16] Adversarial numerical...")

    false_offsets = [-1000, -500, -100, 100, 500, 1000, 1, -1]

    for index, (player, gt) in enumerate(player_run_records):
        if count_category(questions, "adversarial_numerical") >= TARGETS["adversarial_numerical"]:
            break

        actual = gt["object"]
        if not isinstance(actual, int):
            continue

        false_value = max(
            0,
            actual + false_offsets[index % len(false_offsets)],
        )

        make_unique_question(
            questions, seen,
            question=(
                f"Is it correct that {player} scored "
                f"{false_value} ODI runs before {CUTOFF_DATE}?"
            ),
            expected_answer="No",
            question_type="adversarial",
            hallucination_target="numerical_error",
            category="adversarial_numerical",
            ground_truth_ids=[gt["ground_truth_id"]],
            evaluation_policy="yes_no_with_evidence",
            difficulty="hard",
            metadata={
                "player": player,
                "actual_value": actual,
                "false_value": false_value,
            },
        )

    # ========================================================
    # 10. FALSE PREMISE
    # ========================================================

    print("[10/16] False-premise...")

    # Vary both entity and wording so these are not identical duplicates.
    false_entity_templates = [
        "Atlantis XI",
        "Moonlight Cricket Club",
        "Pacific Unicorns",
        "Himalayan Super Kings",
        "Mars XI",
    ]

    false_question_templates = [
        "Which ODI matches did {player} play for {team} before {cutoff}?",
        "How many ODI matches did {player} play for {team} before {cutoff}?",
        "What was {player}'s ODI record for {team} before {cutoff}?",
    ]

    for i in range(TARGETS["false_premise"]):
        player = players[i % len(players)]
        team = false_entity_templates[i % len(false_entity_templates)]
        template = false_question_templates[i % len(false_question_templates)]

        make_unique_question(
            questions, seen,
            question=template.format(
                player=player,
                team=team,
                cutoff=CUTOFF_DATE,
            ),
            expected_answer="Unsupported premise",
            question_type="false_premise",
            hallucination_target="false_premise_acceptance",
            category="false_premise",
            ground_truth_ids=[],
            evaluation_policy="premise_validation",
            difficulty="hard",
            metadata={
                "player": player,
                "false_entity": team,
            },
        )

    # ========================================================
    # 11. FABRICATED ENTITY
    # ========================================================

    print("[11/16] Fabricated entities...")

    fabricated_templates = [
        "How many ODI runs has {name} scored?",
        "How many ODI wickets has {name} taken?",
        "How many ODI matches has {name} played?",
        "Was {name} a player in the ODI records?",
    ]

    for i in range(TARGETS["fabricated_entity"]):
        name = synthetic_name(i)
        template = fabricated_templates[i % len(fabricated_templates)]

        make_unique_question(
            questions, seen,
            question=template.format(name=name),
            expected_answer="Entity not found",
            question_type="entity",
            hallucination_target="fabricated_entity",
            category="fabricated_entity",
            ground_truth_ids=[],
            evaluation_policy="entity_existence",
            difficulty="hard",
            metadata={"fabricated_entity": name},
        )

    # ========================================================
    # 12. UNSUPPORTED CLAIM
    # ========================================================

    print("[12/16] Unsupported claims...")

    unsupported_claims = [
        "favorite color",
        "favorite food",
        "favorite movie",
        "favorite car",
        "favorite song",
        "favorite actor",
        "favorite video game",
        "favorite social-media platform",
        "political preference",
        "personality type",
    ]

    unsupported_templates = [
        "What is {player}'s {claim} according to the ODI records?",
        "According to the ODI records, what is {player}'s {claim}?",
        "Do the ODI records state {player}'s {claim}?",
    ]

    for i in range(TARGETS["unsupported_claim"]):
        player = players[i % len(players)]
        claim = unsupported_claims[i % len(unsupported_claims)]
        template = unsupported_templates[i % len(unsupported_templates)]

        make_unique_question(
            questions, seen,
            question=template.format(
                player=player,
                claim=claim,
            ),
            expected_answer="Unsupported claim",
            question_type="unsupported",
            hallucination_target="unsupported_claim",
            category="unsupported_claim",
            ground_truth_ids=[],
            evaluation_policy="unsupported_claim_detection",
            difficulty="hard",
            metadata={
                "player": player,
                "claim": claim,
            },
        )

    # ========================================================
    # 13. ATTRIBUTE
    # ========================================================

    print("[13/16] Attribute probes...")

    attributes = [
        "batting hand",
        "bowling style",
        "birthplace",
        "height",
        "batting position",
        "jersey number",
        "age",
    ]

    attribute_templates = [
        "What is {player}'s {attribute} according to the cricket records?",
        "Do the cricket records state {player}'s {attribute}?",
        "According to the benchmark source, what is {player}'s {attribute}?",
    ]

    # The current source does not establish these attributes as general
    # ground-truth predicates, so these remain source-support probes.
    for i in range(TARGETS["attribute"]):
        player = players[i % len(players)]
        attribute = attributes[i % len(attributes)]
        template = attribute_templates[i % len(attribute_templates)]

        make_unique_question(
            questions, seen,
            question=template.format(
                player=player,
                attribute=attribute,
            ),
            expected_answer="Not established by benchmark source",
            question_type="attribute",
            hallucination_target="attribute_error",
            category="attribute",
            ground_truth_ids=[],
            evaluation_policy="source_support_required",
            difficulty="hard",
            metadata={
                "player": player,
                "attribute": attribute,
            },
        )

    # ========================================================
    # 14. ALIAS / NICKNAME
    # ========================================================

    print("[14/16] Alias/nickname...")

    alias_templates = [
        "Is '{alias}' an officially recorded name or alias for {player} in the benchmark data?",
        "Does the benchmark source identify '{alias}' as a name or alias of {player}?",
        "Is '{alias}' documented as another name for {player} in the source?",
        "Does the source explicitly record '{alias}' for {player}?",
        "Can the benchmark source verify that '{alias}' refers to {player}?",
    ]

    alias_pairs = []
    for player in players:
        for alias in aliases_for_player(player):
            alias_pairs.append((player, alias))

    for i in range(TARGETS["alias_nickname"]):
        if not alias_pairs:
            break

        player, alias = alias_pairs[i % len(alias_pairs)]
        template = alias_templates[i % len(alias_templates)]

        make_unique_question(
            questions, seen,
            question=template.format(
                player=player,
                alias=alias,
            ),
            expected_answer="Not established by benchmark source",
            question_type="alias",
            hallucination_target="alias_nickname_error",
            category="alias_nickname",
            ground_truth_ids=[],
            evaluation_policy="source_support_required",
            difficulty="hard",
            metadata={
                "player": player,
                "alias": alias,
            },
        )

    # ========================================================
    # 15. AMBIGUOUS NATURAL LANGUAGE
    # ========================================================

    print("[15/16] Ambiguous natural-language questions...")

    ambiguous_templates = [
        ("How many runs did {player} make in one day?", "ambiguous_time_reference"),
        ("How many runs did {player} make in a day?", "ambiguous_time_reference"),
        ("How many runs did {player} make?", "missing_match_context"),
        ("How many wickets did {player} take?", "missing_match_context"),
        ("Who was the best player in this match?", "subjective_question"),
        ("Who is the greatest ODI batsman?", "subjective_question"),
        ("Who was the only player to do this?", "missing_reference"),
        ("How many did he score?", "missing_entity"),
        ("When did he play?", "missing_entity"),
        ("Which team did he play for?", "missing_entity"),
    ]

    for i in range(TARGETS["ambiguous"]):
        template, ambiguity_type = ambiguous_templates[i % len(ambiguous_templates)]

        # Make repeated semantic probes unique by adding a controlled
        # benchmark qualifier rather than creating meaningless duplicates.
        if i >= len(ambiguous_templates):
            player = players[i % len(players)]
            if "{player}" in template:
                question_text = template.format(player=player)
            else:
                question_text = f"{template} (Question context: ODI records.)"
        else:
            player = players[i % len(players)]
            question_text = template.format(player=player)

        make_unique_question(
            questions, seen,
            question=question_text,
            expected_answer="Requires clarification",
            question_type="ambiguous",
            hallucination_target="unsupported_assumption",
            category="ambiguous",
            ground_truth_ids=[],
            evaluation_policy="ambiguity_detection",
            difficulty="hard",
            metadata={
                "ambiguity_type": ambiguity_type,
            },
        )

    # ========================================================
    # 16. UNIQUENESS
    # ========================================================

    print("[16/16] Uniqueness...")

    captain_predicates = {
        "captain",
        "captain_of",
        "team_captain",
        "captaincy",
    }

    wicketkeeper_predicates = {
        "wicketkeeper",
        "wicket_keeper",
        "wicket_keeper_of",
    }

    captain_records = [
        gt for gt in ground_truth
        if gt.get("predicate") in captain_predicates
    ]

    wicketkeeper_records = [
        gt for gt in ground_truth
        if gt.get("predicate") in wicketkeeper_predicates
    ]

    captain_entities = {
        str(gt.get("subject"))
        for gt in captain_records
    }

    wicketkeeper_entities = {
        str(gt.get("subject"))
        for gt in wicketkeeper_records
    }

    intersection = captain_entities & wicketkeeper_entities

    if len(intersection) == 1:
        player = next(iter(intersection))

        ids = [
            gt["ground_truth_id"]
            for gt in captain_records + wicketkeeper_records
            if str(gt.get("subject")) == player
        ]

        make_unique_question(
            questions, seen,
            question="Who is the only wicketkeeper who has also been a captain?",
            expected_answer=player,
            question_type="uniqueness",
            hallucination_target="unsupported_uniqueness",
            category="uniqueness",
            ground_truth_ids=ids,
            evaluation_policy="uniqueness",
            difficulty="hard",
            metadata={
                "condition_1": "wicketkeeper",
                "condition_2": "captain",
                "quantifier": "only",
            },
        )
    else:
        print(
            "No source-backed unique captain/wicketkeeper intersection. "
            "No uniqueness question was invented."
        )

    # ========================================================
    # FINALIZE
    # ========================================================

    random.shuffle(questions)

    for i, question in enumerate(questions, start=1):
        question["question_id"] = f"CRICKET-Q-{i:06d}"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            questions,
            f,
            indent=2,
            ensure_ascii=False,
        )

    category_counts = Counter(q["category"] for q in questions)
    type_counts = Counter(q["question_type"] for q in questions)
    target_counts = Counter(q["hallucination_target"] for q in questions)

    print()
    print("=" * 75)
    print("HalluBench QUESTION GENERATION COMPLETE")
    print("=" * 75)
    print(f"Total questions: {len(questions):,}")

    print("\nQuestion types:")
    for key, value in type_counts.most_common():
        print(f"  {key}: {value:,}")

    print("\nCategories:")
    for key, value in category_counts.most_common():
        print(f"  {key}: {value:,}")

    print("\nHallucination targets:")
    for key, value in target_counts.most_common():
        print(f"  {key}: {value:,}")

    print(f"\nSaved to: {OUTPUT_FILE}")
    print(f"Temporal cutoff: {CUTOFF_DATE}")
    print("=" * 75)


if __name__ == "__main__":
    main()
