from collections import Counter


def calculate_metrics(verdicts):

    total = len(verdicts)

    if total == 0:
        return {
            "total": 0,
            "hallucination_count": 0,
            "hallucination_rate": 0.0,
            "supported_count": 0,
            "supported_rate": 0.0,
            "refusal_correction_count": 0,
            "refusal_correction_rate": 0.0,
            "incorrect_refusal_count": 0,
            "incorrect_refusal_rate": 0.0,
            "answer_failure_count": 0,
            "answer_failure_rate": 0.0,
            "ambiguous_count": 0,
            "ambiguous_rate": 0.0,
        }

    hallucinations = sum(
        1 for x in verdicts
        if x.get("hallucination") is True
    )

    supported = sum(
        1 for x in verdicts
        if x.get("status") == "SUPPORTED"
    )

    correct_refusals = sum(
        1 for x in verdicts
        if x.get("status") == "REFUSAL_CORRECTION"
    )

    incorrect_refusals = sum(
        1 for x in verdicts
        if x.get("status") == "INCORRECT_REFUSAL"
    )

    ambiguous = sum(
        1 for x in verdicts
        if x.get("status") == "AMBIGUOUS"
    )

    # Answer failures include hallucinations and incorrect refusals.
    answer_failures = hallucinations + incorrect_refusals

    status_counts = Counter(
        x.get("status")
        for x in verdicts
    )

    hallucination_types = Counter(
        x.get("hallucination_type")
        for x in verdicts
        if x.get("hallucination_type")
    )

    return {
        "total": total,

        "hallucination_count": hallucinations,
        "hallucination_rate": round(
            hallucinations / total, 4
        ),

        "supported_count": supported,
        "supported_rate": round(
            supported / total, 4
        ),

        "refusal_correction_count": correct_refusals,
        "refusal_correction_rate": round(
            correct_refusals / total, 4
        ),

        "incorrect_refusal_count": incorrect_refusals,
        "incorrect_refusal_rate": round(
            incorrect_refusals / total, 4
        ),

        "answer_failure_count": answer_failures,
        "answer_failure_rate": round(
            answer_failures / total, 4
        ),

        "ambiguous_count": ambiguous,
        "ambiguous_rate": round(
            ambiguous / total, 4
        ),

        "status_distribution": dict(status_counts),

        "hallucination_type_distribution": dict(
            hallucination_types
        ),
    }