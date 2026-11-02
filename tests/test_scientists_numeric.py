import unittest

from evaluation.evaluate_response import (
    numeric_value_present,
    evaluate_scientists_factual,
    SUPPORTED,
    CONTRADICTED
)


class ScientistsNumericTests(unittest.TestCase):

    def test_comma_formatted_integer(self):
        self.assertTrue(
            numeric_value_present(
                "There are 1,625 works.",
                1625
            )
        )

    def test_unformatted_integer(self):
        self.assertTrue(
            numeric_value_present(
                "There are 1625 works.",
                1625
            )
        )

    def test_different_number_not_matched(self):
        self.assertFalse(
            numeric_value_present(
                "There are 16,250 works.",
                1625
            )
        )

    def test_large_comma_formatted_number(self):
        self.assertTrue(
            numeric_value_present(
                "The citation count is 1,103,859.",
                1103859
            )
        )

    def test_decimal_extension_not_matched(self):
        self.assertFalse(
            numeric_value_present(
                "The reported value is 1103859.5.",
                1103859
            )
        )

    def test_number_at_sentence_end(self):
        self.assertTrue(
            numeric_value_present(
                "The total is 1625.",
                1625
            )
        )

    def test_scientists_evaluator_correct_answer(self):
        question = {
            "domain": "scientists",
            "question": "How many works does OpenAlex list?",
            "expected_answer": 1625,
            "ground_truth_fact_id": "test_fact",
            "source": "OpenAlex"
        }

        answer = "According to OpenAlex, there are 1,625 works."

        result = evaluate_scientists_factual(
            question,
            answer
        )

        self.assertEqual(result["status"], SUPPORTED)
        self.assertFalse(result["hallucination"])
        self.assertEqual(
            result["matched_expected_values"],
            ["1625"]
        )
        self.assertEqual(
            result["missing_expected_values"],
            []
        )

    def test_scientists_evaluator_wrong_answer(self):
        question = {
            "domain": "scientists",
            "question": "How many works does OpenAlex list?",
            "expected_answer": 1625
        }

        answer = "According to OpenAlex, there are 1,6250 works."

        result = evaluate_scientists_factual(
            question,
            answer
        )

        self.assertEqual(result["status"], CONTRADICTED)
        self.assertTrue(result["hallucination"])


if __name__ == "__main__":
    unittest.main()