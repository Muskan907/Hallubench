import json
import hashlib
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data/final/crm/ground_truth.jsonl"
OUTPUT_FILE = ROOT / "data/final/crm/questions.jsonl"
SUMMARY_FILE = ROOT / "data/final/crm/question_summary.json"


def make_id(gt_id, question_type):
    raw = f"{gt_id}_{question_type}"
    return "crm_q_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_questions(gt):
    evidence = gt.get("customer_evidence", [])
    responses = gt.get("company_responses", [])
    attribute = gt.get("attribute", "customer experience")
    conversation_id = gt.get("conversation_id")

    customer_texts = [
        item.get("text", "")
        for item in evidence if item.get("text")
    ]

    company_texts = [
        item.get("text", "")
        for item in responses if item.get("text")
    ]

    if not customer_texts:
        return []

    context = {
        "conversation_id": conversation_id,
        "customer_messages": customer_texts,
        "company_messages": company_texts
    }

    questions = []

    # 1. Customer report understanding
    questions.append({
        "question_id": make_id(gt["ground_truth_id"], "customer_report"),
        "ground_truth_id": gt["ground_truth_id"],
        "domain": "crm",
        "question_type": "customer_report",
        "question": (
            f"What did the customer report or describe regarding "
            f"{attribute.replace('_', ' ')}?"
        ),
        "accepted_answers": customer_texts,
        "evidence": evidence,
        "context": context,
        "attribute": attribute,
        "conversation_id": conversation_id,
        "answerability": "source_supported"
    })

    # 2. Exact evidence retrieval
    questions.append({
        "question_id": make_id(gt["ground_truth_id"], "evidence_retrieval"),
        "ground_truth_id": gt["ground_truth_id"],
        "domain": "crm",
        "question_type": "evidence_retrieval",
        "question": (
            f"Which customer message provides evidence about "
            f"{attribute.replace('_', ' ')}?"
        ),
        "accepted_answers": customer_texts,
        "evidence": evidence,
        "context": context,
        "attribute": attribute,
        "conversation_id": conversation_id,
        "answerability": "source_supported"
    })

    # 3. Company response context
    questions.append({
        "question_id": make_id(
            gt["ground_truth_id"], "company_response_context"
        ),
        "ground_truth_id": gt["ground_truth_id"],
        "domain": "crm",
        "question_type": "company_response_context",
        "question": (
            "What did the company say in response to the customer's "
            "messages in this conversation?"
        ),
        "accepted_answers": company_texts if company_texts else [
            "No company response is present in this conversation."
        ],
        "evidence": responses,
        "context": context,
        "attribute": attribute,
        "conversation_id": conversation_id,
        "answerability": "source_supported"
    })

    return questions


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM QUESTION GENERATION")
    print("=" * 65)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    total_gt = 0
    total_questions = 0
    type_counts = Counter()
    category_counts = Counter()
    seen_ids = set()

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            if not line.strip():
                continue

            gt = json.loads(line)
            total_gt += 1

            generated = generate_questions(gt)

            for question in generated:
                qid = question["question_id"]

                if qid in seen_ids:
                    raise ValueError(f"Duplicate question ID: {qid}")

                seen_ids.add(qid)

                output.write(
                    json.dumps(question, ensure_ascii=False) + "\n"
                )

                total_questions += 1
                type_counts[question["question_type"]] += 1
                category_counts[question["attribute"]] += 1

            if total_gt % 50000 == 0:
                print(
                    f"Processed {total_gt:,} ground-truth records..."
                )

    summary = {
        "domain": "crm",
        "source_dataset": "customer_support_on_twitter",
        "total_ground_truth_records": total_gt,
        "total_questions": total_questions,
        "unique_question_ids": len(seen_ids),
        "question_type_counts": dict(type_counts),
        "attribute_counts": dict(category_counts),
        "question_types": [
            "customer_report",
            "evidence_retrieval",
            "company_response_context"
        ],
        "answerability": "source_supported",
        "note": (
            "Questions are generated from customer and company messages. "
            "Company responses are not treated as proof of issue resolution."
        )
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("CRM QUESTION GENERATION COMPLETED")
    print("=" * 65)
    print(f"Ground-truth records: {total_gt:,}")
    print(f"Questions generated: {total_questions:,}")
    print(f"Unique question IDs: {len(seen_ids):,}")

    print("\nQuestion type counts:")
    for name, count in type_counts.items():
        print(f"{name}: {count:,}")

    print(f"\nQuestions: {OUTPUT_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
