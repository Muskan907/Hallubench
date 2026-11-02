
import json
import unittest
from pathlib import Path

from evaluation.evaluate_response import evaluate_answer


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "final" / "scientists"


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class ScientistsOfflinePipelineTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.factual = load_jsonl(DATA / "questions.jsonl")
        cls.challenges = load_jsonl(DATA / "challenge_questions.jsonl")
        cls.ground_truth = load_jsonl(DATA / "ground_truth.jsonl")

    def evaluate(self, question, answer):
        return evaluate_answer(question, answer, self.ground_truth)

    def test_dataset_loading(self):
        self.assertGreater(len(self.factual), 0)
        self.assertGreater(len(self.challenges), 0)
        self.assertGreater(len(self.ground_truth), 0)

    def test_factual_numeric_answer(self):
        question = next(
            q for q in self.factual
            if q.get("question_type") == "bibliometrics"
            and isinstance(q.get("expected_answer"), (int, float))
        )
        expected = question["expected_answer"]

        result = self.evaluate(question, f"The reported value is {expected:,}.")

        self.assertEqual(result["status"], "SUPPORTED")
        self.assertFalse(result["hallucination"])

    def test_false_premise_correction(self):
        question = next(
            q for q in self.challenges
            if q.get("question_type") == "false_premise"
        )
        expected = question["expected_answer"]

        answer = (
            f"No, that premise is incorrect. "
            f"The correct year is {expected}."
        )
        result = self.evaluate(question, answer)

        self.assertEqual(result["status"], "REFUSAL_CORRECTION")
        self.assertFalse(result["hallucination"])

    def test_false_premise_accepted(self):
        question = next(
            q for q in self.challenges
            if q.get("question_type") == "false_premise"
        )

        result = self.evaluate(
            question,
            "Yes, that statement is correct."
        )

        self.assertTrue(result["hallucination"])

    def test_ambiguous_question(self):
        question = next(
            q for q in self.challenges
            if q.get("question_type") == "ambiguous"
        )

        result = self.evaluate(
            question,
            "There are multiple scientists with that name. "
            "Could you clarify which person you mean?"
        )

        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertFalse(result["hallucination"])

    def test_unsupported_evidence_refusal(self):
        question = next(
            q for q in self.challenges
            if q.get("question_type") == "unsupported_evidence"
        )

        result = self.evaluate(
            question,
            "The available dataset does not contain this information, "
            "so I cannot verify it."
        )

        self.assertEqual(result["status"], "REFUSAL_CORRECTION")
        self.assertFalse(result["hallucination"])

    def test_unsupported_evidence_fabrication(self):
        question = next(
            q for q in self.challenges
            if q.get("question_type") == "unsupported_evidence"
        )

        result = self.evaluate(
            question,
            "The scientist definitely received the 2024 Global Science Award."
        )

        self.assertTrue(result["hallucination"])

    def test_all_challenge_types_present(self):
        types = {
            q.get("question_type")
            for q in self.challenges
        }

        self.assertTrue({
            "false_premise",
            "ambiguous",
            "unsupported_evidence"
        }.issubset(types))


if __name__ == "__main__":
    unittest.main(verbosity=2)
