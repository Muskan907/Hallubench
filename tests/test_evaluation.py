from evaluation.evaluate_response import evaluate_answer


def test_supported():
    question = {
        "question_id": "TEST-001",
        "question": "How many ODI runs has Virat Kohli scored?",
        "question_type": "factual",
        "category": "numerical",
        "hallucination_target": "numerical_error",
        "evaluation_policy": "numeric_exact",
        "ground_truth_ids": ["GT-1"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-1",
            "subject": "Virat Kohli",
            "predicate": "career_runs",
            "object": 13784,
        }
    ]

    result = evaluate_answer(
        question,
        "Virat Kohli has scored 13,784 ODI runs.",
        ground_truth,
    )

    assert result["status"] == "SUPPORTED"
    assert result["hallucination"] is False


def test_wrong_number():
    question = {
        "question_id": "TEST-002",
        "question": "How many ODI runs has Virat Kohli scored?",
        "question_type": "factual",
        "category": "numerical",
        "hallucination_target": "numerical_error",
        "evaluation_policy": "numeric_exact",
        "ground_truth_ids": ["GT-1"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-1",
            "subject": "Virat Kohli",
            "predicate": "career_runs",
            "object": 13784,
        }
    ]

    result = evaluate_answer(
        question,
        "Virat Kohli has scored 15000 ODI runs.",
        ground_truth,
    )

    assert result["status"] == "CONTRADICTED"
    assert result["hallucination"] is True


def test_unsupported_claim():
    question = {
        "question_id": "TEST-003",
        "question": "What is Virat Kohli's favorite color according to ODI records?",
        "question_type": "unsupported",
        "category": "unsupported_claim",
        "hallucination_target": "unsupported_claim",
    }

    result = evaluate_answer(
        question,
        "Virat Kohli's favorite color is blue.",
        [],
    )

    assert result["status"] == "UNSUPPORTED"
    assert result["hallucination"] is True


def test_false_premise_correction():
    question = {
        "question_id": "TEST-004",
        "question": "Which ODI matches did Atlantis XI play?",
        "question_type": "false_premise",
        "category": "false_premise",
        "hallucination_target": "false_premise_acceptance",
    }

    result = evaluate_answer(
        question,
        "There is no Atlantis XI in the ODI records.",
        [],
    )

    assert result["status"] == "REFUSAL_CORRECTION"
    assert result["hallucination"] is False


def test_ambiguous_question():
    question = {
        "question_id": "TEST-005",
        "question": "How many runs did Virat Kohli make in one day?",
        "question_type": "ambiguous",
        "category": "ambiguous",
        "hallucination_target": "unsupported_assumption",
    }

    result = evaluate_answer(
        question,
        "This is ambiguous because one day could refer to different matches.",
        [],
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["hallucination"] is False
    assert result["ambiguity_detected"] is True


def test_gemini_conflicting_numerical_answer():
    question = {
        "question_id": "CRICKET-Q-000001",
        "question": "How many sixes has V Shankar scored in ODIs?",
        "question_type": "factual",
        "category": "numerical",
        "hallucination_target": "numerical_error",
        "evaluation_policy": "numeric_exact",
        "ground_truth_ids": ["GT-SIXES"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-SIXES",
            "subject": "V Shankar",
            "predicate": "career_sixes",
            "object": 4,
        }
    ]

    answer = (
        "Vijay Shankar has hit 2 sixes "
        "(or by some records, 3 sixes)."
    )

    result = evaluate_answer(question, answer, ground_truth)

    assert result["status"] == "CONTRADICTED"
    assert result["hallucination"] is True
    assert result["answer_consistency"] == "multiple_numeric_values"
    assert result["answer_numeric_values"] == ["2", "3"]


def test_gemini_incorrect_refusal_with_existing_ground_truth():
    question = {
        "question_id": "CRICKET-Q-000002",
        "question": "Which side won ODI 736439?",
        "question_type": "factual",
        "category": "relationship",
        "hallucination_target": "relationship_error",
        "evaluation_policy": "entity_normalized",
        "ground_truth_ids": ["GT-WINNER"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-WINNER",
            "subject": "736439",
            "predicate": "winner",
            "object": "South Africa",
        }
    ]

    answer = (
        "I am not confident which specific match "
        "that ID corresponds to, and cannot reliably identify the winner."
    )

    result = evaluate_answer(question, answer, ground_truth)

    assert result["status"] == "INCORRECT_REFUSAL"
    assert result["hallucination"] is False
    assert result["failure_type"] == "incorrect_refusal"


def test_partial_multi_fact_answer_is_not_supported():
    question = {
        "question_id": "TEST-008",
        "question": "Give both players' ODI run totals.",
        "question_type": "multi_entity",
        "category": "multi_entity",
        "hallucination_target": "entity_mixing",
        "ground_truth_ids": ["GT-A", "GT-B"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-A",
            "subject": "Player A",
            "predicate": "career_runs",
            "object": 10000,
        },
        {
            "ground_truth_id": "GT-B",
            "subject": "Player B",
            "predicate": "career_runs",
            "object": 9000,
        },
    ]

    result = evaluate_answer(
        question,
        "Player A scored 10000 runs and Player B scored 8500 runs.",
        ground_truth,
    )

    assert result["status"] == "CONTRADICTED"
    assert result["hallucination"] is True
    assert result["matched_ground_truth_ids"] == ["GT-A"]
    assert result["contradicted_ground_truth_ids"] == ["GT-B"]


def test_valid_match_id_not_found_is_incorrect_refusal():
    question = {
        "question_id": "TEST-009",
        "question": "Which side won ODI 736439?",
        "question_type": "factual",
        "category": "relationship",
        "hallucination_target": "relationship_error",
        "ground_truth_ids": ["GT-VALID"],
    }

    ground_truth = [
        {
            "ground_truth_id": "GT-VALID",
            "subject": "736439",
            "predicate": "winner",
            "object": "South Africa",
        }
    ]

    result = evaluate_answer(
        question,
        "There is no match numbered 736439.",
        ground_truth,
    )

    assert result["status"] == "INCORRECT_REFUSAL"
    assert result["hallucination"] is False