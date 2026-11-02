
import json
import unittest
from pathlib import Path

from evaluation.evaluate_response import evaluate_answer


ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "data" / "final"

SAMPLE_LIMIT = 200
CHUNK_SIZE = 1024 * 1024


def iter_json_array(path):
    """Stream objects from a large JSON array without loading it all."""

    decoder = json.JSONDecoder()

    with open(path, "r", encoding="utf-8") as f:
        buffer = ""
        position = 0
        started = False
        eof = False

        while True:
            if position >= len(buffer) and not eof:
                buffer = f.read(CHUNK_SIZE)
                position = 0

                if not buffer:
                    eof = True

            while position < len(buffer) and (
                buffer[position].isspace()
                or buffer[position] == ","
            ):
                position += 1

            if position >= len(buffer):
                if eof:
                    return
                continue

            if not started:
                if buffer[position] != "[":
                    raise ValueError(
                        f"Expected a JSON array in {path}"
                    )

                position += 1
                started = True
                continue

            if buffer[position] == "]":
                return

            try:
                item, end = decoder.raw_decode(buffer, position)

            except json.JSONDecodeError:
                if eof:
                    raise

                # Keep the incomplete object and append another chunk.
                buffer = buffer[position:] + f.read(CHUNK_SIZE)
                position = 0

                if len(buffer) == 0:
                    return

                eof = f.tell() == path.stat().st_size
                continue

            position = end
            yield item

            # Release already-processed content periodically.
            if position >= CHUNK_SIZE:
                buffer = buffer[position:]
                position = 0


def iter_questions(path):
    """Stream questions from either JSON or JSONL."""

    if path is None or not path.exists():
        return

    if path.suffix.lower() == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    else:
        yield from iter_json_array(path)


def read_questions(path, limit=SAMPLE_LIMIT):
    """Read a limited sample of questions."""

    if path is None or not path.exists():
        return []

    results = []

    for question in iter_questions(path):
        results.append(question)

        if len(results) >= limit:
            break

    return results


def find_question(path, question_type):
    """Search the complete file for a particular question type."""

    if path is None or not path.exists():
        return None

    for question in iter_questions(path):
        if question.get("question_type") == question_type:
            return question

    return None


def first_file(folder, candidates):
    for name in candidates:
        path = folder / name

        if path.exists():
            return path

    return None


def require_question(test, path, question_type):
    """Find a required challenge or fail with a useful message."""

    question = find_question(path, question_type)

    test.assertIsNotNone(
        question,
        f"Could not find challenge type '{question_type}' "
        f"in {path}"
    )

    return question


class AllDomainsOfflineTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.datasets = {}

        domain_files = {
            "cricket": {
                "questions": [
                    "questions.json",
                    "questions.jsonl",
                    "pilot_sample_100.json",
                    "pilot_sample_100.jsonl",
                ],
                "challenges": [
                    "challenge_questions.json",
                    "challenge_questions.jsonl",
                    "challenge_pilot_100.json",
                    "challenge_pilot_100.jsonl",
                ],
            },
            "qcommerce": {
                "questions": [
                    "questions.jsonl",
                    "pilot_sample_100.jsonl",
                    "pilot_100.jsonl",
                ],
                "challenges": [
                    "challenge_questions.jsonl",
                    "challenge_pilot_100.jsonl",
                ],
            },
            "crm": {
                "questions": [
                    "questions.jsonl",
                    "pilot_sample_100.jsonl",
                    "pilot_100.jsonl",
                ],
                "challenges": [
                    "challenge_questions.jsonl",
                    "challenge_pilot_100.jsonl",
                ],
            },
            "cinema": {
                "questions": [
                    "questions.jsonl",
                    "pilot_sample_100.jsonl",
                    "pilot_100.jsonl",
                ],
                "challenges": [
                    "challenge_questions.jsonl",
                    "challenge_pilot_100.jsonl",
                ],
            },
            "scientists": {
                "questions": [
                    "questions.jsonl",
                    "pilot_sample_100.jsonl",
                    "pilot_100.jsonl",
                ],
                "challenges": [
                    "challenge_questions.jsonl",
                    "challenge_pilot_100.jsonl",
                ],
            },
        }

        for domain, filenames in domain_files.items():
            folder = FINAL / domain

            if not folder.exists():
                continue

            question_file = first_file(
                folder,
                filenames["questions"]
            )

            challenge_file = first_file(
                folder,
                filenames["challenges"]
            )

            cls.datasets[domain] = {
                "questions": read_questions(question_file),
                "challenges": read_questions(challenge_file),
                "question_file": question_file,
                "challenge_file": challenge_file,
                "folder": folder,
            }

    def evaluate(self, question, answer, ground_truth=None):
        return evaluate_answer(
            question,
            answer,
            ground_truth or []
        )

    def test_all_five_domain_folders_exist(self):
        domains = [
            "cricket",
            "qcommerce",
            "crm",
            "cinema",
            "scientists",
        ]

        for domain in domains:
            self.assertTrue(
                (FINAL / domain).exists(),
                f"Missing domain folder: {domain}"
            )

    def test_all_domains_have_questions(self):
        for domain, data in self.datasets.items():
            self.assertGreater(
                len(data["questions"]),
                0,
                f"No factual questions found for {domain}. "
                f"File: {data['question_file']}"
            )

    def test_question_ids_are_unique(self):
        for domain, data in self.datasets.items():
            ids = [
                q.get("question_id")
                for q in data["questions"] + data["challenges"]
                if q.get("question_id")
            ]

            self.assertEqual(
                len(ids),
                len(set(ids)),
                f"Duplicate question IDs in {domain}"
            )

    def test_all_questions_have_required_fields(self):
        for domain, data in self.datasets.items():
            for q in data["questions"] + data["challenges"]:
                self.assertTrue(
                    q.get("question_id"),
                    f"Missing question_id in {domain}"
                )

                self.assertTrue(
                    q.get("question"),
                    f"Missing question text in {domain}"
                )

                self.assertEqual(
                    q.get("domain"),
                    domain,
                    f"Incorrect domain in {domain}"
                )

    def test_scientists_pipeline(self):
        data = self.datasets["scientists"]
        factual = data["questions"]
        challenge_file = data["challenge_file"]

        q = next(
            (
                item for item in factual
                if isinstance(
                    item.get("expected_answer"),
                    (int, float)
                )
            ),
            None
        )

        self.assertIsNotNone(
            q,
            "No numeric Scientists factual question in sample"
        )

        result = self.evaluate(
            q,
            f"The reported value is {q['expected_answer']:,}."
        )

        self.assertEqual(result["status"], "SUPPORTED")

        q = require_question(
            self,
            challenge_file,
            "false_premise"
        )

        result = self.evaluate(
            q,
            f"No, that is incorrect. "
            f"The correct year is {q['expected_answer']}."
        )

        self.assertEqual(
            result["status"],
            "REFUSAL_CORRECTION"
        )

        q = require_question(
            self,
            challenge_file,
            "ambiguous"
        )

        result = self.evaluate(
            q,
            "Multiple scientists share this name. "
            "Could you clarify which person?"
        )

        self.assertEqual(
            result["status"],
            "AMBIGUOUS"
        )

        q = require_question(
            self,
            challenge_file,
            "unsupported_evidence"
        )

        result = self.evaluate(
            q,
            "The supplied dataset does not contain this information."
        )

        self.assertEqual(
            result["status"],
            "REFUSAL_CORRECTION"
        )

    def test_cinema_pipeline(self):
        challenge_file = self.datasets["cinema"]["challenge_file"]

        q = require_question(
            self,
            challenge_file,
            "false_premise"
        )

        result = self.evaluate(
            q,
            "No, that is an incorrect premise."
        )

        self.assertEqual(
            result["status"],
            "REFUSAL_CORRECTION"
        )

        q = require_question(
            self,
            challenge_file,
            "ambiguous"
        )

        result = self.evaluate(
            q,
            "Multiple films share this title. "
            "Please clarify which film."
        )

        self.assertEqual(
            result["status"],
            "AMBIGUOUS"
        )

        q = require_question(
            self,
            challenge_file,
            "unsupported_evidence"
        )

        result = self.evaluate(
            q,
            "The supplied dataset does not contain this information."
        )

        self.assertEqual(
            result["status"],
            "REFUSAL_CORRECTION"
        )

    def test_qcommerce_pipeline(self):
        data = self.datasets["qcommerce"]["questions"]

        q = next(
            (
                item for item in data
                if item.get("question_type") == "verification_boundary"
            ),
            None
        )

        self.assertIsNotNone(
            q,
            "No Q-Commerce verification_boundary question in sample"
        )

        result = self.evaluate(
            q,
            "The reviewer reports this, but it cannot be independently verified."
        )

        self.assertEqual(
            result["status"],
            "REFUSAL_CORRECTION"
        )

        result = self.evaluate(
            q,
            "This product definitely has that quality."
        )

        self.assertEqual(
            result["status"],
            "UNSUPPORTED"
        )

    def test_crm_pipeline(self):
        data = self.datasets["crm"]["questions"]

        q = next(
            (
                item for item in data
                if item.get("question_type") == "customer_report"
                and item.get("context", {}).get("customer_messages")
            ),
            None
        )

        self.assertIsNotNone(
            q,
            "No CRM customer_report question with customer messages"
        )

        messages = q["context"]["customer_messages"]
        answer = " ".join(messages)

        result = self.evaluate(q, answer)

        self.assertEqual(
            result["status"],
            "SUPPORTED"
        )

    def test_cricket_question_routing(self):
        data = self.datasets["cricket"]["questions"]

        self.assertGreater(
            len(data),
            0,
            "Cricket questions were not loaded"
        )

        q = data[0]

        self.assertEqual(
            q.get("domain"),
            "cricket"
        )

        result = self.evaluate(
            q,
            "I cannot verify this answer."
        )

        self.assertIn("status", result)
        self.assertIn("hallucination", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
