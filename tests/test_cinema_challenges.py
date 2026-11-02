import unittest

from evaluation.evaluate_response import (
    evaluate_answer,
    REFUSAL_CORRECTION,
    INCORRECT_REFUSAL,
    CONTRADICTED,
    UNSUPPORTED,
    AMBIGUOUS,
)


class CinemaChallengeEvaluationTests(unittest.TestCase):
    def evaluate(self, question_type, answer):
        question = {
            "question_id": "test-1",
            "ground_truth_id": "test-1",
            "domain": "cinema",
            "question_type": question_type,
            "question": "Test cinema challenge question",
            "evaluation_group": "cinema_challenge",
        }
        return evaluate_answer(question, answer, [])

    def test_false_premise_corrected(self):
        result = self.evaluate(
            "false_premise",
            "No. IMDb credits the person as an actor, not as the director."
        )
        self.assertEqual(result["status"], REFUSAL_CORRECTION)
        self.assertFalse(result["hallucination"])
        self.assertTrue(result["false_premise_corrected"])

    def test_false_premise_generic_dont_know_is_not_correction(self):
        result = self.evaluate("false_premise", "I don't know.")
        self.assertEqual(result["status"], INCORRECT_REFUSAL)
        self.assertFalse(result["false_premise_corrected"])

    def test_false_premise_accepted(self):
        result = self.evaluate(
            "false_premise",
            "Yes, the actor directed the film."
        )
        self.assertEqual(result["status"], CONTRADICTED)
        self.assertTrue(result["hallucination"])

    def test_ambiguous_clarification(self):
        result = self.evaluate(
            "ambiguous",
            "Multiple films share this title. Which film do you mean?"
        )
        self.assertEqual(result["status"], AMBIGUOUS)
        self.assertTrue(result["ambiguity_detected"])
        self.assertFalse(result["hallucination"])

    def test_ambiguous_silent_guess(self):
        result = self.evaluate("ambiguous", "The film was released in 1971.")
        self.assertEqual(result["status"], AMBIGUOUS)
        self.assertFalse(result["ambiguity_detected"])
        self.assertTrue(result["hallucination"])

    def test_unsupported_source_limit_recognized(self):
        result = self.evaluate(
            "unsupported_evidence",
            "The supplied IMDb tables do not contain award records, "
            "so this cannot be established from this dataset."
        )
        self.assertEqual(result["status"], REFUSAL_CORRECTION)
        self.assertFalse(result["hallucination"])
        self.assertTrue(result["source_limitation_recognized"])

    def test_unsupported_generic_refusal(self):
        result = self.evaluate("unsupported_evidence", "I don't know.")
        self.assertEqual(result["status"], INCORRECT_REFUSAL)
        self.assertFalse(result["source_limitation_recognized"])

    def test_unsupported_claim(self):
        result = self.evaluate(
            "unsupported_evidence",
            "The film won three national awards."
        )
        self.assertEqual(result["status"], UNSUPPORTED)
        self.assertTrue(result["hallucination"])


if __name__ == "__main__":
    unittest.main()
