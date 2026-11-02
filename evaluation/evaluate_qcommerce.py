import argparse
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_QUESTIONS = ROOT / "data/final/qcommerce/pilot_sample_100.json"
DEFAULT_GROUND_TRUTH = ROOT / "data/final/qcommerce/ground_truth.jsonl"
RESPONSES_DIR = ROOT / "results/responses"
VERDICTS_DIR = ROOT / "results/verdicts"
METRICS_DIR = ROOT / "results/metrics"

VERDICTS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} in {path}: {exc}"
                )

    return records


def save_json(path, data):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize(text):
    text = str(text or "").casefold()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


REFUSAL_PATTERNS = [
    "i don't know",
    "i do not know",
    "cannot determine",
    "can't determine",
    "not enough information",
    "insufficient information",
    "unable to answer",
    "cannot answer",
    "can't answer",
    "i cannot verify",
    "i can't verify"
]


def is_refusal(answer):
    text = normalize(answer)
    return any(normalize(p) in text for p in REFUSAL_PATTERNS)


def contains_evidence(answer, evidence):
    normalized_answer = normalize(answer)
    normalized_evidence = normalize(evidence)

    if not normalized_answer or not normalized_evidence:
        return False

    return normalized_evidence in normalized_answer


def evaluate_evidence_question(question, answer):
    evidence = question.get("evidence", "")

    if is_refusal(answer):
        return {
            "status": "INCORRECT_REFUSAL",
            "hallucination": False,
            "failure_type": "incorrect_refusal",
            "reason": "Source-backed review evidence exists, but the model refused."
        }

    if contains_evidence(answer, evidence):
        return {
            "status": "SUPPORTED",
            "hallucination": False,
            "failure_type": None,
            "reason": "The response contains the source-supported evidence phrase."
        }

    return {
        "status": "REVIEW_REQUIRED",
        "hallucination": None,
        "failure_type": "semantic_answer_review",
        "reason": (
            "The response does not reproduce the exact evidence phrase. "
            "It may be a valid paraphrase or an inaccurate answer and needs "
            "semantic review."
        )
    }


def evaluate_verification_boundary(answer):
    text = normalize(answer)

    supported_patterns = [
        r"only.{0,80}(customer|reviewer|review).{0,80}(report|reported|claim|experience)",
        r"(does not|doesnt|cannot|cant).{0,80}(independently|objectively|prove|establish|verify)",
        r"not independently (verified|confirmed|established)",
        r"review alone.{0,80}(does not|doesnt|cannot|cant)",
        r"customer report.{0,80}(not proof|not evidence of independent verification)",
        r"does not prove",
        r"cannot independently verify",
        r"cannot establish an objective",
        r"not enough evidence to conclude"
    ]

    contradicted_patterns = [
        r"proves? that",
        r"confirms? that",
        r"verified that",
        r"definitely (has|had|was|is)",
        r"objectively (has|had|was|is)",
        r"independently verified",
        r"establishes? that.{0,80}(defect|fault|damage)"
    ]

    if any(re.search(pattern, text) for pattern in supported_patterns):
        return {
            "status": "SUPPORTED",
            "hallucination": False,
            "failure_type": None,
            "reason": (
                "The answer recognizes that a customer review alone "
                "does not independently verify an objective defect."
            )
        }

    if any(re.search(pattern, text) for pattern in contradicted_patterns):
        return {
            "status": "CONTRADICTED",
            "hallucination": True,
            "failure_type": "unsupported_objective_claim",
            "reason": (
                "The answer appears to treat a customer report as "
                "independent proof of an objective defect."
            )
        }

    return {
        "status": "REVIEW_REQUIRED",
        "hallucination": None,
        "failure_type": "semantic_boundary_review",
        "reason": (
            "The answer requires semantic review to determine whether "
            "it correctly distinguishes reported experience from "
            "independent verification."
        )
    }


def evaluate_question(question, answer, ground_truth_lookup):
    question_type = question.get("question_type")

    ground_truth_id = question.get("ground_truth_id")
    ground_truth = ground_truth_lookup.get(ground_truth_id)

    if ground_truth is None:
        return {
            "status": "DATA_LINK_ERROR",
            "hallucination": None,
            "failure_type": "missing_ground_truth_link",
            "reason": "The question's ground_truth_id was not found."
        }

    if normalize(ground_truth.get("evidence")) != normalize(
        question.get("evidence")
    ):
        return {
            "status": "DATA_LINK_ERROR",
            "hallucination": None,
            "failure_type": "evidence_link_mismatch",
            "reason": "Question evidence does not match its ground-truth record."
        }

    if question_type in {"reviewer_report", "evidence_retrieval"}:
        result = evaluate_evidence_question(question, answer)

    elif question_type == "verification_boundary":
        result = evaluate_verification_boundary(answer)

    else:
        result = {
            "status": "UNSUPPORTED_QUESTION_TYPE",
            "hallucination": None,
            "failure_type": "unknown_question_type",
            "reason": f"Unknown question type: {question_type}"
        }

    result.update({
        "question_id": question.get("question_id"),
        "ground_truth_id": ground_truth_id,
        "question_type": question_type,
        "attribute": question.get("attribute"),
        "source_dataset": question.get("source_dataset"),
        "source_record_id": question.get("source_record_id"),
        "question": question.get("question"),
        "answer": answer,
        "expected_answer": question.get("expected_answer"),
        "evidence": question.get("evidence")
    })

    return result


def calculate_qcommerce_metrics(verdicts):
    total = len(verdicts)
    status_counts = Counter(v.get("status") for v in verdicts)

    determinate = [
        v for v in verdicts
        if v.get("status") in {"SUPPORTED", "CONTRADICTED"}
    ]

    hallucinations = sum(
        1 for v in verdicts if v.get("hallucination") is True
    )

    incorrect_refusals = status_counts["INCORRECT_REFUSAL"]
    review_required = status_counts["REVIEW_REQUIRED"]

    metrics = {
        "domain": "qcommerce",
        "total_evaluated": total,
        "supported_count": status_counts["SUPPORTED"],
        "contradicted_count": status_counts["CONTRADICTED"],
        "hallucination_count": hallucinations,
        "incorrect_refusal_count": incorrect_refusals,
        "review_required_count": review_required,
        "data_link_error_count": status_counts["DATA_LINK_ERROR"],
        "unsupported_question_type_count": status_counts[
            "UNSUPPORTED_QUESTION_TYPE"
        ],
        "status_distribution": dict(status_counts),
        "automatic_decision_count": len(determinate),
        "automatic_hallucination_rate": (
            round(hallucinations / len(determinate), 4)
            if determinate else None
        ),
        "review_coverage": (
            round((total - review_required) / total, 4)
            if total else 0.0
        )
    }

    by_type = defaultdict(list)

    for verdict in verdicts:
        by_type[verdict.get("question_type", "unknown")].append(verdict)

    metrics["question_type_metrics"] = {}

    for question_type, rows in by_type.items():
        counts = Counter(row.get("status") for row in rows)
        decided = [
            row for row in rows
            if row.get("status") in {"SUPPORTED", "CONTRADICTED"}
        ]
        hallucinations_for_type = sum(
            1 for row in rows if row.get("hallucination") is True
        )

        metrics["question_type_metrics"][question_type] = {
            "total": len(rows),
            "status_distribution": dict(counts),
            "hallucination_count": hallucinations_for_type,
            "automatic_decision_count": len(decided),
            "automatic_hallucination_rate": (
                round(hallucinations_for_type / len(decided), 4)
                if decided else None
            ),
            "review_required_count": counts["REVIEW_REQUIRED"]
        }

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Q-Commerce HalluBench responses."
    )

    parser.add_argument("--provider", required=True)
    parser.add_argument("--responses", default=None)
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    parser.add_argument("--run-name", default="pilot100")

    args = parser.parse_args()

    provider = args.provider.lower()

    responses_file = (
        Path(args.responses)
        if args.responses
        else RESPONSES_DIR / f"{provider}_qcommerce_{args.run_name}.jsonl"
    )

    if not responses_file.is_absolute():
        responses_file = ROOT / responses_file

    questions = load_json(args.questions)
    ground_truth_records = load_jsonl(args.ground_truth)
    responses = load_jsonl(responses_file)

    question_lookup = {
        row["question_id"]: row for row in questions
    }

    ground_truth_lookup = {
        row["ground_truth_id"]: row for row in ground_truth_records
    }

    print("\nHALLUBENCH Q-COMMERCE EVALUATION")
    print("=" * 52)
    print("Provider:", provider)
    print("Questions:", len(questions))
    print("Ground truth records:", len(ground_truth_records))
    print("Response records:", len(responses))

    verdicts = []
    skipped = 0
    unmatched = 0
    review_required = 0

    for response in responses:
        if response.get("status") != "success":
            skipped += 1
            continue

        question_id = response.get("question_id")
        question = question_lookup.get(question_id)

        if question is None:
            unmatched += 1
            continue

        answer = response.get("answer") or ""

        verdict = evaluate_question(
            question,
            answer,
            ground_truth_lookup
        )

        verdict["provider"] = response.get("provider", provider)
        verdict["model"] = response.get("model")
        verdict["latency_seconds"] = response.get("latency_seconds")
        verdict["usage"] = response.get("usage")
        verdict["timestamp_utc"] = response.get("timestamp_utc")

        if verdict["status"] == "REVIEW_REQUIRED":
            review_required += 1

        verdicts.append(verdict)

    if not verdicts:
        print("\nNo successful matching responses to evaluate.")
        print("Skipped:", skipped)
        print("Unmatched:", unmatched)
        return

    metrics = calculate_qcommerce_metrics(verdicts)

    metrics.update({
        "provider": provider,
        "models": sorted({
            str(v.get("model"))
            for v in verdicts if v.get("model")
        }),
        "response_file": str(responses_file),
        "skipped_responses": skipped,
        "unmatched_responses": unmatched,
        "review_required_count": review_required,
        "evaluation_method": (
            "Exact evidence matching and rule-based verification-boundary "
            "classification. Semantic paraphrases are marked for manual review."
        )
    })

    verdicts_path = (
        VERDICTS_DIR /
        f"qcommerce_{provider}_{args.run_name}_evaluation.json"
    )

    metrics_path = (
        METRICS_DIR /
        f"qcommerce_{provider}_{args.run_name}_metrics.json"
    )

    save_json(verdicts_path, verdicts)
    save_json(metrics_path, metrics)

    print("\nEVALUATION COMPLETED")
    print("=" * 52)
    print("Responses evaluated:", len(verdicts))
    print("Skipped responses:", skipped)
    print("Unmatched responses:", unmatched)
    print("Supported:", metrics["supported_count"])
    print("Contradicted:", metrics["contradicted_count"])
    print("Incorrect refusals:", metrics["incorrect_refusal_count"])
    print("Review required:", metrics["review_required_count"])
    print("Automatic hallucination rate:", metrics["automatic_hallucination_rate"])

    print("\nVerdicts:", verdicts_path)
    print("Metrics:", metrics_path)


if __name__ == "__main__":
    main()
