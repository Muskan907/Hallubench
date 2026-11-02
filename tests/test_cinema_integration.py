import unittest

from evaluation.evaluate_response import (
    SUPPORTED,
    CONTRADICTED,
    evaluate_answer,
)


class CinemaEvaluationTests(unittest.TestCase):
    def test_movie_title_supported(self):
        question = {
            "question_id": "q1",
            "ground_truth_id": "gt1",
            "domain": "cinema",
            "question_type": "movie_information",
            "question": "What is the title of movie tt0000001?",
            "accepted_answers": ["Example Film"],
        }
        result = evaluate_answer(question, "The film is Example Film.", [])
        self.assertEqual(result["status"], SUPPORTED)

    def test_cast_member_supported(self):
        question = {
            "question_id": "q2",
            "ground_truth_id": "gt2",
            "domain": "cinema",
            "question_type": "cast_relationship",
            "question": "Which person is credited as actor in Example Film?",
            "accepted_answers": [{
                "name": "Example Actor",
                "role": "actor",
                "characters": '["Hero"]',
            }],
        }
        result = evaluate_answer(question, "Example Actor played the lead.", [])
        self.assertEqual(result["status"], SUPPORTED)

    def test_wrong_rating_contradicted(self):
        question = {
            "question_id": "q3",
            "ground_truth_id": "gt3",
            "domain": "cinema",
            "question_type": "numerical",
            "question": "What is the IMDb rating?",
            "accepted_answers": [8.2],
        }
        result = evaluate_answer(question, "The rating is 7.2.", [])
        self.assertEqual(result["status"], CONTRADICTED)


if __name__ == "__main__":
    unittest.main()
