
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluate_response import evaluate_answer
from evaluation.metrics import calculate_metrics


RESPONSES_DIR = PROJECT_ROOT / "results" / "responses"
VERDICTS_DIR = PROJECT_ROOT / "results" / "verdicts"
METRICS_DIR = PROJECT_ROOT / "results" / "metrics"

DOMAIN_FILES = {
    "cricket": {
        "questions": "questions.json",
        "ground_truth": "ground_truth.json",
        "load_ground_truth": True,
    },
    "qcommerce": {
        "questions": "questions.jsonl",
        "ground_truth": "ground_truth.jsonl",
        "load_ground_truth": False,
    },
    "crm": {
        "questions": "questions.jsonl",
        "ground_truth": "ground_truth.jsonl",
        "load_ground_truth": False,
    },
    "cinema": {
        "questions": "questions.jsonl",
        "ground_truth": "ground_truth.jsonl",
        "load_ground_truth": False,
    },
    "scientists": {
        "questions": "questions.jsonl",
        "ground_truth": "ground_truth.jsonl",
        "load_ground_truth": False,
    },
}


def load_records(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file:\n{path}")

    if path.suffix.lower() == ".jsonl":
        records = []
        with open(path, "r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON on line {line_number} in {path}: {error}"
                    ) from error
        return records

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("questions", "records", "data"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError(f"Expected a list of records in {path}")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def add_breakdowns(metrics, verdicts):
    for field, output_key in (
        ("question_type", "by_question_type"),
        ("attribute", "by_attribute"),
        ("evaluation_group", "by_evaluation_group"),
        ("category", "by_category"),
    ):
        groups = defaultdict(list)

        for verdict in verdicts:
            value = verdict.get(field) or "unclassified"
            groups[str(value)].append(verdict)

        metrics[output_key] = {
            name: calculate_metrics(group)
            for name, group in sorted(groups.items())
        }


def find_response_file(provider, domain, run_name=None):
    candidates = []

    if run_name:
        candidates.extend([
            RESPONSES_DIR / f"{provider}_{run_name}.jsonl",
            RESPONSES_DIR / f"{domain}_{provider}_{run_name}.jsonl",
        ])

    candidates.extend([
        RESPONSES_DIR / f"{provider}_{domain}.jsonl",
        RESPONSES_DIR / f"{domain}_{provider}.jsonl",
        RESPONSES_DIR / f"{provider}.jsonl",
    ])

    for path in candidates:
        if path.exists():
            return path

    checked = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Could not find a response file. Checked:\n" + checked
    )


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate HalluBench responses across all five domains."
    )

    parser.add_argument(
        "--domain",
        required=True,
        choices=list(DOMAIN_FILES.keys()),
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=["openai", "gemini", "claude", "grok", "deepseek", "qwen"],
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional response run name, such as scientists_test.",
    )
    parser.add_argument(
        "--responses-file",
        default=None,
        help="Optional explicit response JSONL path.",
    )

    args = parser.parse_args()

    domain = args.domain
    provider = args.provider
    config = DOMAIN_FILES[domain]

    domain_dir = PROJECT_ROOT / "data" / "final" / domain
    questions_file = domain_dir / config["questions"]
    ground_truth_file = domain_dir / config["ground_truth"]

    if args.responses_file:
        responses_file = Path(args.responses_file)
        if not responses_file.is_absolute():
            responses_file = PROJECT_ROOT / responses_file
    else:
        responses_file = find_response_file(
            provider, domain, args.run_name
        )

    print("=" * 70)
    print("HALLUBENCH EVALUATION")
    print("=" * 70)
    print(f"Domain:       {domain}")
    print(f"Provider:     {provider}")
    print(f"Questions:    {questions_file}")
    print(f"Responses:    {responses_file}")

    questions = load_records(questions_file)
    responses = load_records(responses_file)

    ground_truth = []

    if config["load_ground_truth"]:
        ground_truth = load_records(ground_truth_file)

    print(f"\nLoaded questions: {len(questions):,}")
    print(f"Loaded responses: {len(responses):,}")
    print(f"Loaded ground truth records: {len(ground_truth):,}")

    question_lookup = {
        item["question_id"]: item
        for item in questions
        if item.get("question_id")
    }

    verdicts = []
    skipped = 0
    unmatched = 0
    duplicate_responses = 0
    evaluated_ids = set()

    for index, response in enumerate(responses, start=1):
        if response.get("status") != "success":
            skipped += 1
            continue

        question_id = response.get("question_id")
        question = question_lookup.get(question_id)

        if question is None:
            unmatched += 1
            continue

        if question_id in evaluated_ids:
            duplicate_responses += 1
            continue

        answer = response.get("answer")

        if answer is None or not str(answer).strip():
            skipped += 1
            continue

        verdict = evaluate_answer(
            question,
            answer,
            ground_truth,
        )

        verdict["provider"] = response.get("provider", provider)
        verdict["model"] = response.get("model")
        verdict["latency_seconds"] = response.get("latency_seconds")
        verdict["usage"] = response.get("usage")
        verdict["response_timestamp_utc"] = response.get("timestamp_utc")

        verdict["ground_truth_id"] = question.get("ground_truth_id")
        verdict["conversation_id"] = question.get("conversation_id")
        verdict["attribute"] = question.get("attribute")
        verdict["evaluation_group"] = question.get("evaluation_group")

        verdicts.append(verdict)
        evaluated_ids.add(question_id)

        if index % 100 == 0:
            print(f"Processed {index:,}/{len(responses):,} response records")

    if not verdicts:
        print("\nNo successful responses were available to evaluate.")
        print(f"Skipped: {skipped}")
        print(f"Unmatched: {unmatched}")
        return

    metrics = calculate_metrics(verdicts)

    metrics.update({
        "domain": domain,
        "provider": provider,
        "response_file": str(responses_file),
        "question_file": str(questions_file),
        "evaluated_responses": len(verdicts),
        "skipped_responses": skipped,
        "unmatched_responses": unmatched,
        "duplicate_responses": duplicate_responses,
        "evaluation_method": "domain_specific_rules_and_lexical_baselines",
    })

    add_breakdowns(metrics, verdicts)

    run_suffix = args.run_name or responses_file.stem
    verdicts_file = VERDICTS_DIR / f"{domain}_{provider}_{run_suffix}.json"
    metrics_file = METRICS_DIR / f"{domain}_{provider}_{run_suffix}.json"

    save_json(verdicts_file, verdicts)
    save_json(metrics_file, metrics)

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"Evaluated:          {len(verdicts):,}")
    print(f"Skipped:            {skipped:,}")
    print(f"Unmatched:          {unmatched:,}")
    print(f"Duplicate records:  {duplicate_responses:,}")
    print(f"Hallucinations:     {metrics.get('hallucination_count', 0):,}")
    print(f"Hallucination rate: {metrics.get('hallucination_rate', 0):.2%}")
    print(f"Unverified:         {metrics.get('unverified_count', 0):,}")
    print(f"\nVerdicts: {verdicts_file}")
    print(f"Metrics:  {metrics_file}")


if __name__ == "__main__":
    main()
