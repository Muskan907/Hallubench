import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from collections import Counter

from .normalize import normalize_text, normalize_name, normalize_number, extract_numbers, contains_value


SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNSUPPORTED = "UNSUPPORTED"
AMBIGUOUS = "AMBIGUOUS"
REFUSAL_CORRECTION = "REFUSAL_CORRECTION"
INCORRECT_REFUSAL = "INCORRECT_REFUSAL"
UNVERIFIED = "UNVERIFIED"


def is_refusal_or_correction(answer):
    text = normalize_text(answer)

    patterns = [
        "i don't know",
        "i do not know",
        "cannot determine",
        "can't determine",
        "cannot be determined",
        "can't be determined",
        "not enough information",
        "insufficient information",
        "not available in the records",
        "not provided in the records",
        "the records do not show",
        "the records don't show",
        "there is no evidence",
        "no evidence",
        "cannot verify",
        "can't verify",
        "not supported by the records",
        "the premise is false",
        "this premise is false",
        "the premise appears false",
        "there is no such",
        "there is no",
        "does not exist in the records",
        "doesn't exist in the records",
        "not found in the records",
        "not present in the records",
        "not recorded in the records",
        "i am not confident",
        "i'm not confident",
        "cannot reliably identify",
        "can't reliably identify",
        "unable to identify",
        "unable to determine",
        "i cannot identify",
        "i can't identify",
        "not a valid",
        "invalid match",
    ]

    return any(pattern in text for pattern in patterns)

def get_ground_truth(question, ground_truth):
    ids = question.get("ground_truth_ids", [])

    if isinstance(ids, str):
        ids = [ids]

    # CRM uses a singular ground_truth_id.
    singular_id = question.get("ground_truth_id")
    if singular_id:
        ids.append(singular_id)

    ids = set(ids)

    if not ids:
        return []

    return [
        record for record in ground_truth
        if record.get("ground_truth_id") in ids
    ]


def get_numeric_values(answer):
    values = extract_numbers(answer) or []
    normalized = set()

    for value in values:
        try:
            normalized.add(str(normalize_number(value)))
        except (TypeError, ValueError):
            continue

    return normalized


def evaluate_factual(question, answer, ground_truth):
    records = get_ground_truth(question, ground_truth)

    target = question.get("hallucination_target", "unsupported_claim")

    if not records:
        return {
            "status": UNSUPPORTED,
            "hallucination": True,
            "failure_type": "missing_ground_truth",
            "hallucination_type": target,
            "reason": "No linked ground-truth record.",
            "matched_ground_truth_ids": [],
            "contradicted_ground_truth_ids": [],
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "incorrect_refusal",
            "hallucination_type": None,
            "reason": "The model refused, but linked source-backed evidence exists.",
            "matched_ground_truth_ids": [],
            "contradicted_ground_truth_ids": [
                record["ground_truth_id"] for record in records
            ],
        }

    matched = []
    contradicted = []

    for record in records:
        if contains_value(answer, record.get("object")):
            matched.append(record["ground_truth_id"])
        else:
            contradicted.append(record["ground_truth_id"])

    if matched and not contradicted:
        return {
            "status": SUPPORTED,
            "hallucination": False,
            "failure_type": None,
            "hallucination_type": None,
            "reason": "All linked source-backed values are present.",
            "matched_ground_truth_ids": matched,
            "contradicted_ground_truth_ids": [],
        }

    if matched and contradicted:
        return {
            "status": CONTRADICTED,
            "hallucination": True,
            "failure_type": "partial_fact_mismatch",
            "hallucination_type": target,
            "reason": "Some expected values are missing or conflict with the answer.",
            "matched_ground_truth_ids": matched,
            "contradicted_ground_truth_ids": contradicted,
        }

    result = {
        "status": CONTRADICTED,
        "hallucination": True,
        "failure_type": "incorrect_factual_answer",
        "hallucination_type": target,
        "reason": "Answer does not contain the expected source-backed value.",
        "matched_ground_truth_ids": [],
        "contradicted_ground_truth_ids": contradicted,
    }

    if normalize_text(question.get("evaluation_policy", "")) == "numeric_exact":
        numeric_values = get_numeric_values(answer)
        result["answer_numeric_values"] = sorted(numeric_values)
        result["answer_consistency"] = (
            "multiple_numeric_values"
            if len(numeric_values) > 1
            else "single_or_no_numeric_value"
        )

    return result


def tokenize_evidence(text):
    text = normalize_text(text)

    # URLs and social-media handles are not useful for semantic matching.
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#\w+", " ", text)

    tokens = re.findall(r"[a-z0-9]+", text)

    stopwords = {
        "the", "a", "an", "is", "are", "was", "were",
        "to", "of", "and", "or", "in", "on", "at",
        "it", "this", "that", "i", "we", "you", "they",
        "he", "she", "my", "our", "your", "their",
        "for", "with", "from", "as", "by", "be", "been",
        "has", "have", "had", "do", "does", "did",
    }

    return [token for token in tokens if token not in stopwords]


def calculate_text_match(answer, evidence_text):
    answer_tokens = set(tokenize_evidence(answer))
    evidence_tokens = set(tokenize_evidence(evidence_text))

    if not answer_tokens or not evidence_tokens:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }

    overlap = answer_tokens.intersection(evidence_tokens)

    precision = len(overlap) / len(answer_tokens)
    recall = len(overlap) / len(evidence_tokens)

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate_crm(question, answer):
    question_type = question.get("question_type", "")
    evidence = question.get("evidence", [])
    context = question.get("context", {})

    if question_type in {"customer_report", "evidence_retrieval"}:
        expected_messages = context.get("customer_messages", [])
        evidence_records = [
            item for item in evidence
            if item.get("text") in expected_messages
        ]
    elif question_type == "company_response_context":
        expected_messages = context.get("company_messages", [])
        evidence_records = [
            item for item in evidence
            if item.get("text") in expected_messages
        ]
    else:
        return {
            "status": UNVERIFIED,
            "hallucination": None,
            "failure_type": "unknown_crm_question_type",
            "reason": "CRM question type is not recognized.",
            "evidence_match_score": 0.0,
            "matched_evidence_ids": [],
        }

    if not expected_messages:
        return {
            "status": UNVERIFIED,
            "hallucination": None,
            "failure_type": "no_expected_messages",
            "reason": "No relevant source messages are available for this question.",
            "evidence_match_score": 0.0,
            "matched_evidence_ids": [],
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "incorrect_refusal",
            "reason": "Relevant source messages are available, but the model refused.",
            "evidence_match_score": 0.0,
            "matched_evidence_ids": [],
        }

    expected_text = " ".join(expected_messages)
    scores = calculate_text_match(answer, expected_text)

    matched_ids = []

    for item in evidence_records:
        item_score = calculate_text_match(answer, item.get("text", ""))

        if item_score["f1"] >= 0.30:
            matched_ids.append(item.get("message_id"))

    # Conservative threshold for this lexical baseline.
    if scores["f1"] >= 0.45:
        status = SUPPORTED
        reason = "Answer has sufficient lexical overlap with the relevant source messages."
        hallucination = False
        failure_type = None
    else:
        status = UNVERIFIED
        reason = (
            "The lexical matcher could not establish sufficient evidence overlap. "
            "This is not, by itself, proof of hallucination."
        )
        hallucination = None
        failure_type = "insufficient_lexical_evidence"

    return {
        "status": status,
        "hallucination": hallucination,
        "failure_type": failure_type,
        "hallucination_type": None,
        "reason": reason,
        "evidence_match_score": scores["f1"],
        "evidence_precision": scores["precision"],
        "evidence_recall": scores["recall"],
        "matched_evidence_ids": matched_ids,
        "expected_evidence_count": len(expected_messages),
        "question_type": question_type,
        "attribute": question.get("attribute"),
        "conversation_id": question.get("conversation_id"),
        "ground_truth_id": question.get("ground_truth_id"),
    }


def evaluate_qcommerce(question, answer):
    """
    Q-Commerce evaluation based on the original customer review.
    Customer claims are not treated as independently verified product facts.
    """
    import re

    def normalize(value):
        return re.sub(r"\s+", " ", str(value or "").lower()).strip()

    qtype = normalize(question.get("question_type"))
    answer_text = normalize(answer)

    review = normalize(
        question.get("review_context")
        or question.get("evidence")
        or ""
    )

    if not answer_text:
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "empty_answer",
            "reason": "The model returned an empty answer.",
            "evaluator": "qcommerce_review_evidence",
        }

    if qtype == "reviewer_reporter":
        # This question asks what the reviewer personally reported.
        # Use accepted answers when supplied, but do not claim objective truth.
        accepted = question.get("accepted_answers") or []
        if not isinstance(accepted, list):
            accepted = [accepted]

        expected = [
            normalize(x.get("text") if isinstance(x, dict) else x)
            for x in accepted
        ]
        expected = [x for x in expected if x]

        matched = [
            value for value in expected
            if value in answer_text or answer_text in value
        ]

        if matched:
            status = SUPPORTED
            hallucination = False
            reason = "The response matches a recorded reviewer report."
        elif review and any(
            token in answer_text
            for token in review.split()
            if len(token) >= 6
        ):
            status = UNVERIFIED
            hallucination = None
            reason = (
                "Some review language overlaps, but the response "
                "does not match an accepted answer exactly."
            )
        else:
            status = UNVERIFIED
            hallucination = None
            reason = (
                "The lexical baseline cannot reliably verify this "
                "reviewer-report paraphrase."
            )

        return {
            "status": status,
            "hallucination": hallucination,
            "failure_type": None if status == SUPPORTED else "paraphrase_unverified",
            "reason": reason,
            "matched_expected_answers": matched,
            "evaluator": "qcommerce_review_evidence",
        }

    if qtype == "evidence_retrieval":
        accepted = question.get("accepted_answers") or []
        if not isinstance(accepted, list):
            accepted = [accepted]

        expected = [
            normalize(x.get("text") if isinstance(x, dict) else x)
            for x in accepted
        ]
        expected = [x for x in expected if x]

        matched = [
            value for value in expected
            if value and value in answer_text
        ]

        if expected and len(matched) == len(expected):
            return {
                "status": SUPPORTED,
                "hallucination": False,
                "failure_type": None,
                "reason": "All expected evidence terms were found.",
                "matched_expected_answers": matched,
                "evaluator": "qcommerce_review_evidence",
            }

        return {
            "status": UNVERIFIED,
            "hallucination": None,
            "failure_type": "evidence_paraphrase_unverified",
            "reason": (
                "The exact lexical baseline could not verify the "
                "evidence retrieval answer."
            ),
            "matched_expected_answers": matched,
            "evaluator": "qcommerce_review_evidence",
        }

    if qtype == "verification_boundary":
        # Correct behavior must distinguish review reports from verified facts.
        boundary_markers = (
            "the review says",
            "the reviewer reports",
            "customer reported",
            "according to the review",
            "cannot independently verify",
            "not independently verified",
            "the review does not establish",
            "based only on the review",
        )

        recognized_boundary = any(
            marker in answer_text for marker in boundary_markers
        )

        if recognized_boundary:
            return {
                "status": REFUSAL_CORRECTION,
                "hallucination": False,
                "failure_type": None,
                "reason": (
                    "The model distinguished a customer report "
                    "from independently verified product truth."
                ),
                "verification_boundary_recognized": True,
                "evaluator": "qcommerce_verification_boundary",
            }

        return {
            "status": UNSUPPORTED,
            "hallucination": True,
            "failure_type": "verification_boundary_violation",
            "hallucination_type": "customer_report_misrepresented_as_fact",
            "reason": (
                "The answer did not clearly distinguish customer "
                "reported evidence from independently verified truth."
            ),
            "verification_boundary_recognized": False,
            "evaluator": "qcommerce_verification_boundary",
        }

    return {
        "status": UNVERIFIED,
        "hallucination": None,
        "failure_type": "unknown_qcommerce_question_type",
        "reason": f"Unsupported Q-Commerce question type: {qtype}",
        "evaluator": "qcommerce_review_evidence",
    }


def recognizes_source_limitation(answer):
    text = normalize_text(answer)
    patterns = [
        "not included in the supplied dataset",
        "not available in the supplied dataset",
        "not present in the supplied dataset",
        "dataset does not contain",
        "dataset doesn't contain",
        "source does not contain",
        "source doesn't contain",
        "no awards data",
        "no award data",
        "awards data is not included",
        "award records are not available",
        "cannot be established from this dataset",
        "cannot be determined from this dataset",
        "cannot verify from the supplied data",
        "not supported by the supplied data",
        "not provided in the supplied tables",
        "the supplied tables do not contain",
        "the available tables do not contain",
        "the dataset has no awards table",
        "there is no awards table",
    ]
    return any(pattern in text for pattern in patterns)


def recognizes_false_premise(answer):
    text = normalize_text(answer)

    patterns = [
        r"^\s*no\b.{0,160}\b(not|never|no)\b.{0,80}\b(director|directing|directed)\b",
        r"\bnot credited as (the )?director\b",
        r"\bnot (the |a )?director\b",
        r"\bwas not (the |a )?director\b",
        r"\bwere not (the |a )?director\b",
        r"\bnot listed as (the )?director\b",
        r"\bnot recorded as (the )?director\b",
        r"\bno director credit\b",
        r"\bdoes not have a director credit\b",
        r"\bincorrect premise\b",
        r"\bfalse premise\b",
        r"\bthe premise is incorrect\b",
        r"\bthe premise is false\b",
        r"\bcredited as an actor, not as (the )?director\b",
        r"\bactor rather than (the )?director\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def recognizes_ambiguity(answer):
    text = normalize_text(answer)
    patterns = [
        "please clarify",
        "could you clarify",
        "which film do you mean",
        "which movie do you mean",
        "multiple films share this title",
        "more than one film has this title",
        "several films share this title",
        "need more context",
        "not enough context",
        "the title is ambiguous",
        "this title is ambiguous",
        "could refer to multiple films",
        "could mean multiple films",
        "which version are you referring to",
        "which release are you referring to",
        "there are multiple films",
        "there is more than one film",
    ]
    return any(pattern in text for pattern in patterns)


def evaluate_unsupported(question, answer):
    if recognizes_source_limitation(answer):
        return {
            "status": REFUSAL_CORRECTION,
            "hallucination": False,
            "failure_type": None,
            "hallucination_type": None,
            "reason": (
                "Model correctly identified that the requested information "
                "is absent from the supplied source."
            ),
            "source_limitation_recognized": True,
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "generic_refusal_without_source_limitation",
            "hallucination_type": None,
            "reason": (
                "Model expressed uncertainty but did not identify the "
                "specific limitation of the supplied source."
            ),
            "source_limitation_recognized": False,
        }

    return {
        "status": UNSUPPORTED,
        "hallucination": True,
        "failure_type": "unsupported_assertion",
        "hallucination_type": question.get(
            "hallucination_target", "unsupported_claim"
        ),
        "reason": "Model supplied information not supported by the source.",
        "source_limitation_recognized": False,
    }


def evaluate_false_premise(question, answer):
    if recognizes_false_premise(answer):
        return {
            "status": REFUSAL_CORRECTION,
            "hallucination": False,
            "failure_type": None,
            "hallucination_type": None,
            "reason": "Model explicitly rejected or corrected the false premise.",
            "false_premise_corrected": True,
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "unsubstantiated_refusal",
            "hallucination_type": None,
            "reason": (
                "Model expressed uncertainty without explicitly correcting "
                "the false premise."
            ),
            "false_premise_corrected": False,
        }

    return {
        "status": CONTRADICTED,
        "hallucination": True,
        "failure_type": "false_premise_acceptance",
        "hallucination_type": "false_premise_acceptance",
        "reason": "Model did not correct the false premise.",
        "false_premise_corrected": False,
    }


def evaluate_ambiguous(question, answer):
    detected = recognizes_ambiguity(answer)

    return {
        "status": AMBIGUOUS,
        "hallucination": not detected,
        "failure_type": None if detected else "unacknowledged_ambiguity",
        "hallucination_type": None if detected else "unsupported_assumption",
        "ambiguity_detected": detected,
        "reason": (
            "Model recognized the ambiguity and requested clarification."
            if detected
            else (
                "Model failed to acknowledge the ambiguity and may have "
                "assumed one interpretation."
            )
        ),
    }


# Cinema uses accepted answers embedded in each question. The full 4 GB
# ground-truth JSONL is therefore not loaded during evaluation.
CINEMA_DB = Path(__file__).resolve().parent.parent / "data" / "processed" / "cinema" / "cinema.db"


@lru_cache(maxsize=50000)
def cinema_person_name(nconst):
    if not nconst or not CINEMA_DB.exists():
        return None
    connection = sqlite3.connect(CINEMA_DB)
    try:
        row = connection.execute(
            "SELECT name FROM people WHERE nconst = ?", (nconst,)
        ).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def _cinema_expected_terms(question):
    answers = question.get("accepted_answers") or []
    if not isinstance(answers, list):
        answers = [answers]

    qtype = question.get("question_type", "")
    terms = []

    for answer in answers:
        if isinstance(answer, dict):
            # Cast facts store person name, role and character metadata.
            if answer.get("name"):
                terms.append(str(answer["name"]))
            # Indian-market alternate-title facts are verified by the title.
            elif answer.get("title"):
                terms.append(str(answer["title"]))
        elif isinstance(answer, (int, float)):
            terms.append(str(answer))
        elif isinstance(answer, str):
            value = answer.strip()
            if qtype == "movie_information" and "genre" in normalize_text(question.get("question", "")):
                terms.extend(part.strip() for part in value.split(",") if part.strip())
            elif qtype in {"director_relationship", "writer_relationship"}:
                # The current ground-truth builder stored nconst IDs for
                # directors/writers. Resolve those IDs to person names.
                ids = [part.strip() for part in value.split(",") if part.strip()]
                names = [cinema_person_name(person_id) for person_id in ids]
                terms.extend(name for name in names if name)
                if not names or not any(names):
                    # Never label a response hallucinated when IDs cannot
                    # be resolved to source-backed names.
                    terms.append("__CINEMA_PERSON_LOOKUP_UNAVAILABLE__")
            elif qtype == "numerical":
                terms.append(value)
            else:
                terms.append(value)

    return [term for term in terms if term]


def evaluate_cinema(question, answer):
    qtype = question.get("question_type", "")
    expected = _cinema_expected_terms(question)

    if not expected or "__CINEMA_PERSON_LOOKUP_UNAVAILABLE__" in expected:
        return {
            "status": UNVERIFIED,
            "hallucination": None,
            "failure_type": "cinema_expected_value_unavailable",
            "hallucination_type": None,
            "reason": "Cinema expected value could not be resolved from the local source database.",
            "matched_ground_truth_ids": [],
            "contradicted_ground_truth_ids": [],
            "evaluator": "exact_lexical_baseline"
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "incorrect_refusal",
            "hallucination_type": None,
            "reason": "A source-backed expected answer exists, but the model refused.",
            "matched_ground_truth_ids": [],
            "contradicted_ground_truth_ids": [question.get("ground_truth_id")],
            "evaluator": "exact_lexical_baseline"
        }

    normalized_answer = normalize_text(answer)
    raw_answer = str(answer)
    matched_terms = []
    missing_terms = []

    for term in expected:
        normalized_term = normalize_text(term)
        if not normalized_term:
            continue

        if qtype == "numerical":
            # Numeric facts require the expected numeric token, not a
            # substring match (for example, 8 must not match 18).
            raw_term = str(term).strip()
            pattern = r"(?<!\d)" + re.escape(raw_term) + r"(?!\d)"
            found = re.search(pattern, raw_answer) is not None
        else:
            found = normalized_term in normalized_answer

        if found:
            matched_terms.append(term)
        else:
            missing_terms.append(term)

    if matched_terms and not missing_terms:
        status = SUPPORTED
        hallucination = False
        failure_type = None
        reason = "All expected cinema answer terms were found in the response."
    elif matched_terms:
        status = CONTRADICTED
        hallucination = True
        failure_type = "partial_expected_value_match"
        reason = "The response included only some expected cinema answer terms."
    else:
        status = CONTRADICTED
        hallucination = True
        failure_type = "expected_value_not_found"
        reason = "The response did not contain the expected source-backed cinema answer."

    return {
        "status": status,
        "hallucination": hallucination,
        "failure_type": failure_type,
        "hallucination_type": "cinema_factual_mismatch" if hallucination else None,
        "reason": reason,
        "expected_terms": expected,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "matched_ground_truth_ids": (
            [question.get("ground_truth_id")] if matched_terms else []
        ),
        "contradicted_ground_truth_ids": (
            [question.get("ground_truth_id")] if missing_terms else []
        ),
        "evaluator": "exact_lexical_baseline"
    }


# ============================================================
# SCIENTISTS DOMAIN
# ============================================================

def scientist_expected_values(value):
    if value is None:
        return []

    if isinstance(value, dict):
        return [
            str(value[k])
            for k in ("doi", "title")
            if value.get(k)
        ]

    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(scientist_expected_values(item))
        return result

    value = str(value).strip()
    return [value] if value else []


def scientist_exact_number(answer, value):
    return re.search(
        r"(?<!\d)" + re.escape(str(value)) + r"(?!\d)",
        str(answer)
    ) is not None


def evaluate_scientists_factual(question, answer):

    expected = question.get("expected_answer")
    values = scientist_expected_values(expected)

    if not values:
        return {
            "status": UNVERIFIED,
            "hallucination": None,
            "failure_type": "missing_expected_answer",
            "reason": "No embedded expected answer is available.",
            "evaluator": "scientists_exact_value_baseline"
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "incorrect_refusal",
            "reason": (
                "Source-backed expected evidence exists, "
                "but the model refused."
            ),
            "evaluator": "scientists_exact_value_baseline"
        }

    matched = []
    missing = []

    # Numeric expected answer
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):

        if numeric_value_present(answer, expected):
            matched.append(str(expected))
        else:
            missing.append(str(expected))

    # Dictionary expected answer, such as DOI and publication title
    elif isinstance(expected, dict):

        for value in values:
            if contains_value(answer, value):
                matched.append(str(value))
            else:
                missing.append(str(value))

    # String or list expected answer
    else:

        for value in values:
            if contains_value(answer, value):
                matched.append(str(value))
            else:
                missing.append(str(value))

    # Publication records can be identified by either DOI or title.
    if isinstance(expected, dict):
        supported = bool(matched)
    else:
        supported = bool(matched) and not missing

    if supported:
        status = SUPPORTED
        hallucination = False
        failure = None

    elif matched:
        status = CONTRADICTED
        hallucination = True
        failure = "partial_expected_value_match"

    else:
        status = CONTRADICTED
        hallucination = True
        failure = "expected_value_not_found"

    return {
        "status": status,
        "hallucination": hallucination,
        "failure_type": failure,
        "hallucination_type": (
            "scientists_factual_mismatch"
            if hallucination else None
        ),
        "reason": (
            "Expected source-backed value found."
            if supported
            else "Expected source-backed value not fully established in the response."
        ),
        "expected_answer": expected,
        "matched_expected_values": matched,
        "missing_expected_values": missing,
        "ground_truth_fact_id": question.get("ground_truth_fact_id"),
        "source": question.get("source"),
        "source_url": question.get("source_url"),
        "evaluator": "scientists_exact_value_baseline"
    }


def recognizes_scientist_ambiguity(answer):
    text = normalize_text(answer)

    patterns = [
        "which scientist do you mean",
        "which researcher do you mean",
        "which person are you referring to",
        "please identify the scientist",
        "please clarify which scientist",
        "multiple scientists share this name",
        "more than one scientist has this name",
        "multiple researchers share this name",
        "the name is ambiguous",
        "this name is ambiguous",
        "need the scientist affiliation",
        "need an orcid",
        "need an openalex id",
        "could you provide more context",
        "could you clarify which person"
    ]

    return (
        any(pattern in text for pattern in patterns)
        or recognizes_ambiguity(answer)
    )


def evaluate_scientists_ambiguous(question, answer):
    detected = recognizes_scientist_ambiguity(answer)

    return {
        "status": AMBIGUOUS,
        "hallucination": not detected,
        "failure_type": (
            None if detected else "unacknowledged_scientist_ambiguity"
        ),
        "hallucination_type": (
            None if detected else "unsupported_assumption"
        ),
        "ambiguity_detected": detected,
        "candidate_count": len(question.get("candidate_subjects") or []),
        "reason": (
            "Model recognized the ambiguous scientist identity."
            if detected else
            "Model did not acknowledge the ambiguous identity."
        ),
        "evaluator": "scientists_challenge_rules"
    }


def evaluate_scientists_false_premise(question, answer):
    expected = scientist_expected_values(
        question.get("expected_answer")
    )

    actual_year = expected[0] if expected else ""

    question_years = re.findall(
        r"(?<!\d)(?:18|19|20)\d{2}(?!\d)",
        str(question.get("question", ""))
    )

    wrong_year = question_years[0] if question_years else None

    answer_has_actual = (
        bool(actual_year)
        and scientist_exact_number(answer, actual_year)
    )

    answer_has_wrong = (
        bool(wrong_year)
        and scientist_exact_number(answer, wrong_year)
    )

    answer_normalized = normalize_text(answer)

    correction_markers = [
        "incorrect",
        "not correct",
        "that is false",
        "the correct year",
        "actually received",
        "was awarded in",
        "received the prize in",
        "the award year was",
        "the year was"
    ]

    explicit_correction = any(
        marker in answer_normalized
        for marker in correction_markers
    )

    corrected = (
        answer_has_actual
        and (not answer_has_wrong or explicit_correction)
    ) or (
        recognizes_false_premise(answer)
        and answer_has_actual
    )

    if corrected:
        return {
            "status": REFUSAL_CORRECTION,
            "hallucination": False,
            "failure_type": None,
            "false_premise_corrected": True,
            "reason": "Model corrected the false Nobel award-year premise.",
            "expected_correct_year": actual_year,
            "evaluator": "scientists_challenge_rules"
        }

    if is_refusal_or_correction(answer):
        return {
            "status": INCORRECT_REFUSAL,
            "hallucination": False,
            "failure_type": "unsubstantiated_refusal",
            "false_premise_corrected": False,
            "reason": "Model did not provide the recorded correction.",
            "expected_correct_year": actual_year,
            "evaluator": "scientists_challenge_rules"
        }

    return {
        "status": CONTRADICTED,
        "hallucination": True,
        "failure_type": "false_premise_acceptance",
        "hallucination_type": "false_premise_acceptance",
        "false_premise_corrected": False,
        "reason": "Model failed to correct the incorrect Nobel year.",
        "expected_correct_year": actual_year,
        "evaluator": "scientists_challenge_rules"
    }

def numeric_value_present(answer, expected):
    """
    Compare numeric values while handling thousands separators.

    Examples:
        1,625       matches 1625
        1,103,859   matches 1103859
        16250       does not match 1625
        1103859.5   does not match 1103859
    """
    import re
    from decimal import Decimal, InvalidOperation

    try:
        expected_number = Decimal(
            str(expected).replace(",", "").strip()
        )

        if not expected_number.is_finite():
            return False

        if expected_number == expected_number.to_integral_value():
            expected_text = str(int(expected_number))
        else:
            expected_text = format(
                expected_number.normalize(), "f"
            )

        # Remove commas used as thousands separators.
        normalized_answer = re.sub(
            r"(?<=\d),(?=\d)",
            "",
            str(answer)
        )

        # Allow sentence punctuation after the number.
        # Do not match a longer number or a decimal extension.
        pattern = (
            rf"(?<![\d.])"
            rf"{re.escape(expected_text)}"
            rf"(?!\d)"
            rf"(?!\.\d)"
        )

        return re.search(pattern, normalized_answer) is not None

    except (InvalidOperation, ValueError, TypeError):
        return False

def evaluate_scientists_unsupported(question, answer):
    result = evaluate_unsupported(question, answer)
    result["evaluator"] = "scientists_source_limitation_rules"
    return result


def evaluate_answer(question, answer, ground_truth):
    answer = "" if answer is None else str(answer).strip()

    domain = str(question.get("domain", "")).strip().lower()
    question_type = str(
        question.get("question_type", "")
    ).strip().lower()
    category = str(question.get("category", "")).strip().lower()
    target = str(
        question.get("hallucination_target", "")
    ).strip().lower()

    # if domain == "crm":
    #     result = evaluate_crm(question, answer)
    if domain == "qcommerce":
        result = evaluate_qcommerce(question, answer)
    elif domain == "crm":
        result = evaluate_crm(question, answer)
    elif domain == "scientists" and question_type == "false_premise":
        result = evaluate_scientists_false_premise(question, answer)

    elif domain == "scientists" and question_type == "ambiguous":
        result = evaluate_scientists_ambiguous(question, answer)

    elif domain == "scientists" and question_type == "unsupported_evidence":
        result = evaluate_scientists_unsupported(question, answer)

    elif domain == "scientists":
        result = evaluate_scientists_factual(question, answer)

    elif domain == "cinema" and question_type == "false_premise":
        result = evaluate_false_premise(question, answer)

    elif domain == "cinema" and question_type == "ambiguous":
        result = evaluate_ambiguous(question, answer)

    elif domain == "cinema" and question_type == "unsupported_evidence":
        result = evaluate_unsupported(question, answer)

    elif domain == "cinema":
        result = evaluate_cinema(question, answer)

    elif (
        question_type == "ambiguous"
        or category == "ambiguous"
        or target == "unsupported_assumption"
    ):
        result = evaluate_ambiguous(question, answer)

    elif (
        question_type == "false_premise"
        or category == "false_premise"
        or target == "false_premise_acceptance"
    ):
        result = evaluate_false_premise(question, answer)

    elif (
        question_type in {"unsupported", "unsupported_evidence"}
        or category == "unsupported_claim"
        or target in {
            "unsupported_claim",
            "fabricated_entity",
            "attribute_error",
            "alias_nickname_error"
        }
    ):
        result = evaluate_unsupported(question, answer)

    else:
        result = evaluate_factual(question, answer, ground_truth)

    result.update({
        "question_id": question.get("question_id"),
        "question": question.get("question"),
        "answer": answer,
        "question_type": question.get("question_type"),
        "domain": question.get("domain", "cricket"),
        "category": question.get("category"),
        "evaluation_policy": question.get("evaluation_policy"),
        "hallucination_target": question.get("hallucination_target"),
        "evaluation_group": question.get("evaluation_group")
    })

    return result
