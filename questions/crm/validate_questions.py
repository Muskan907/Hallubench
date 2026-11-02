import json
import sqlite3
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

GT_FILE = ROOT / "data/final/crm/ground_truth.jsonl"
Q_FILE = ROOT / "data/final/crm/questions.jsonl"
REPORT_FILE = ROOT / "data/final/crm/question_validation.json"
DB_FILE = ROOT / "data/processed/crm/question_validation.sqlite"

EXPECTED_TYPES = {
    "customer_report",
    "evidence_retrieval",
    "company_response_context"
}


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM QUESTION VALIDATION")
    print("=" * 65)

    if not GT_FILE.exists() or not Q_FILE.exists():
        raise FileNotFoundError("Ground truth or questions file missing.")

    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_FILE) + suffix)
        if path.exists():
            path.unlink()

    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        CREATE TABLE ground_truth (
            ground_truth_id TEXT PRIMARY KEY,
            attribute TEXT,
            customer_answers TEXT,
            company_answers TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE question_ids (
            question_id TEXT PRIMARY KEY
        )
    """)

    print("\nIndexing ground-truth records...")

    gt_count = 0

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            gt = json.loads(line)

            customer_answers = [
                x.get("text", "")
                for x in gt.get("customer_evidence", [])
            ]

            company_answers = [
                x.get("text", "")
                for x in gt.get("company_responses", [])
            ]

            conn.execute(
                """
                INSERT INTO ground_truth
                VALUES (?, ?, ?, ?)
                """,
                (
                    gt["ground_truth_id"],
                    gt.get("attribute"),
                    json.dumps(customer_answers, ensure_ascii=False),
                    json.dumps(company_answers, ensure_ascii=False)
                )
            )

            gt_count += 1

            if gt_count % 100000 == 0:
                conn.commit()
                print(f"Indexed {gt_count:,} records...")

    conn.commit()

    print(f"Ground-truth records indexed: {gt_count:,}")

    total = 0
    errors = Counter()
    type_counts = Counter()
    attribute_counts = Counter()
    invalid_examples = []

    print("\nValidating questions...")

    with Q_FILE.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue

            total += 1

            try:
                q = json.loads(line)
            except json.JSONDecodeError:
                errors["invalid_json"] += 1
                continue

            qid = q.get("question_id")
            gt_id = q.get("ground_truth_id")
            qtype = q.get("question_type")

            if not qid:
                errors["missing_question_id"] += 1
                continue

            try:
                conn.execute(
                    "INSERT INTO question_ids VALUES (?)",
                    (qid,)
                )
            except sqlite3.IntegrityError:
                errors["duplicate_question_id"] += 1

            gt_row = conn.execute(
                """
                SELECT attribute, customer_answers, company_answers
                FROM ground_truth
                WHERE ground_truth_id = ?
                """,
                (gt_id,)
            ).fetchone()

            if gt_row is None:
                errors["missing_ground_truth_reference"] += 1
                continue

            attribute, customer_json, company_json = gt_row

            type_counts[qtype] += 1
            attribute_counts[attribute] += 1

            if qtype not in EXPECTED_TYPES:
                errors["unexpected_question_type"] += 1

            if not q.get("question", "").strip():
                errors["empty_question"] += 1

            accepted = q.get("accepted_answers", [])

            if not isinstance(accepted, list) or not accepted:
                errors["empty_accepted_answers"] += 1

            elif qtype in {"customer_report", "evidence_retrieval"}:
                expected = json.loads(customer_json)

                if accepted != expected:
                    errors["customer_answer_mismatch"] += 1

            elif qtype == "company_response_context":
                expected = json.loads(company_json)

                if expected:
                    if accepted != expected:
                        errors["company_answer_mismatch"] += 1
                else:
                    expected_no_response = [
                        "No company response is present in this conversation."
                    ]
                    if accepted != expected_no_response:
                        errors["no_response_answer_mismatch"] += 1

            if q.get("attribute") != attribute:
                errors["attribute_mismatch"] += 1

            if len(invalid_examples) < 10 and errors:
                invalid_examples.append({
                    "line": line_number,
                    "question_id": qid,
                    "ground_truth_id": gt_id
                })

            if total % 100000 == 0:
                print(f"Validated {total:,} questions...")

    conn.commit()

    unique_ids = conn.execute(
        "SELECT COUNT(*) FROM question_ids"
    ).fetchone()[0]

    missing_types = EXPECTED_TYPES - set(type_counts)

    report = {
        "domain": "crm",
        "ground_truth_records": gt_count,
        "total_questions": total,
        "unique_question_ids": unique_ids,
        "duplicate_question_ids": errors["duplicate_question_id"],
        "question_type_counts": dict(type_counts),
        "attribute_counts": dict(attribute_counts),
        "missing_question_types": sorted(missing_types),
        "errors": dict(errors),
        "error_count": sum(errors.values()),
        "sample_error_locations": invalid_examples,
        "status": "PASS" if not errors and not missing_types else "FAIL"
    }

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    conn.close()

    print("\n" + "=" * 65)
    print("CRM QUESTION VALIDATION RESULTS")
    print("=" * 65)
    print(f"Ground-truth records: {gt_count:,}")
    print(f"Total questions: {total:,}")
    print(f"Unique question IDs: {unique_ids:,}")
    print(f"Duplicate IDs: {errors['duplicate_question_id']}")
    print(f"Validation errors: {sum(errors.values())}")

    print("\nQuestion types:")
    for name, count in type_counts.items():
        print(f"{name}: {count:,}")

    print(f"\nSTATUS: {report['status']}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
