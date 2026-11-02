import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

PILOT = ROOT / "data/final/crm/pilot_sample_100.json"
MANIFEST = ROOT / "data/final/crm/pilot_sample_100_manifest.json"
REPORT = ROOT / "data/final/crm/pilot_validation.json"


def main():
    print("=" * 65)
    print("HALLUBENCH | CRM PILOT VALIDATION")
    print("=" * 65)

    with PILOT.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    errors = []
    ids = []
    gt_ids = []
    types = Counter()
    attributes = Counter()
    response_status = Counter()

    for index, q in enumerate(questions):
        if not q.get("question_id"):
            errors.append(f"Row {index}: missing question ID")
        else:
            ids.append(q["question_id"])

        if not q.get("ground_truth_id"):
            errors.append(f"Row {index}: missing ground truth ID")
        else:
            gt_ids.append(q["ground_truth_id"])

        if not q.get("question", "").strip():
            errors.append(f"Row {index}: empty question")

        if not q.get("accepted_answers"):
            errors.append(f"Row {index}: empty accepted answers")

        if not q.get("evidence"):
            errors.append(f"Row {index}: missing evidence")

        if q.get("domain") != "crm":
            errors.append(f"Row {index}: incorrect domain")

        types[q.get("question_type")] += 1
        attributes[q.get("attribute")] += 1

        if q.get("question_type") == "company_response_context":
            messages = q.get("context", {}).get("company_messages", [])
            response_status[
                "response_present" if messages else "no_company_response"
            ] += 1

    if len(questions) != 100:
        errors.append(f"Expected 100 questions, got {len(questions)}")

    if len(ids) != len(set(ids)):
        errors.append("Duplicate question IDs found")

    if len(gt_ids) != len(set(gt_ids)):
        errors.append("Duplicate ground-truth records found")

    expected_types = {
        "customer_report": 34,
        "evidence_retrieval": 33,
        "company_response_context": 33
    }

    if dict(types) != expected_types:
        errors.append("Question type distribution does not match expected quotas")

    if len(attributes) != 11:
        errors.append("Expected all 11 CRM categories")

    report = {
        "domain": "crm",
        "sample_size": len(questions),
        "unique_question_ids": len(set(ids)),
        "unique_ground_truth_records": len(set(gt_ids)),
        "question_type_counts": dict(types),
        "attribute_counts": dict(attributes),
        "company_response_status": dict(response_status),
        "errors": errors,
        "error_count": len(errors),
        "status": "PASS" if not errors else "FAIL"
    }

    with REPORT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Questions: {len(questions)}")
    print(f"Unique question IDs: {len(set(ids))}")
    print(f"Unique ground-truth records: {len(set(gt_ids))}")

    print("\nQuestion types:")
    for name, count in types.items():
        print(f"{name}: {count}")

    print("\nCompany response status:")
    for name, count in response_status.items():
        print(f"{name}: {count}")

    print(f"\nErrors: {len(errors)}")
    for error in errors[:20]:
        print(error)

    print(f"\nSTATUS: {report['status']}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
