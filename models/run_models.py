import argparse
import json
import os
import time
import sqlite3
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
RESPONSES_DIR = ROOT / "results" / "responses"
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")

DOMAIN_QUESTION_FILES = {
    "cricket": ROOT / "data/final/cricket/questions.json",
    "qcommerce": ROOT / "data/final/qcommerce/questions.jsonl",
    "crm": ROOT / "data/final/crm/questions.jsonl",
    "cinema": ROOT / "data/final/cinema/questions.jsonl",
    "scientists": ROOT / "data/final/scientists/questions.jsonl",
}

SYSTEM_PROMPT = """
You are answering questions for a factual language-model benchmark.

Answer the user's question naturally and directly.

Important:
- Do not browse the web.
- Do not use external tools.
- Do not invent facts.
- If the question is ambiguous, explain the ambiguity instead of silently assuming.
- If the premise of the question is false, correct the premise.
- If you are not confident that a claim is supported, say so.
- Do not mention this benchmark or its evaluation process.
""".strip()


PROVIDERS = {
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "base_url_env": "OPENAI_BASE_URL",
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
    },
    "claude": {
        "key_env": "ANTHROPIC_API_KEY",
        "model_env": "ANTHROPIC_MODEL",
    },
    "grok": {
        "key_env": "XAI_API_KEY",
        "model_env": "XAI_MODEL",
        "base_url_env": "XAI_BASE_URL",
    },
    "deepseek": {
        "key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "base_url_env": "DEEPSEEK_BASE_URL",
    },
    "qwen": {
        "key_env": "QWEN_API_KEY",
        "model_env": "QWEN_MODEL",
        "base_url_env": "QWEN_BASE_URL",
    },
}


# ============================================================
# QUESTION LOADING
# ============================================================

def load_questions(questions_file):
    questions_file = Path(questions_file)

    if not questions_file.is_absolute():
        questions_file = ROOT / questions_file

    if not questions_file.exists():
        raise FileNotFoundError(
            f"Questions file not found:\n{questions_file}"
        )

    if questions_file.suffix.lower() == ".jsonl":
        questions = []

        with open(questions_file, "r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                try:
                    questions.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSONL on line {line_number}: {error}"
                    ) from error

        return questions

    with open(questions_file, "r", encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(questions, list):
        raise ValueError(
            "Questions file must contain a JSON list or JSONL records."
        )

    return questions


# ============================================================
# CINEMA HELPER
# ============================================================

@lru_cache(maxsize=20000)
def lookup_cinema_title(tconst):
    """Resolve IMDb title IDs to readable titles."""

    db_path = ROOT / "data" / "processed" / "cinema" / "cinema.db"

    if not db_path.exists() or not tconst:
        return None

    connection = sqlite3.connect(db_path)

    try:
        row = connection.execute(
            "SELECT primary_title FROM titles WHERE tconst = ?",
            (tconst,)
        ).fetchone()

        return row[0] if row else None

    finally:
        connection.close()


# ============================================================
# PROMPT BUILDER
# ============================================================

def build_prompt(question):

    if not isinstance(question, dict):
        return f"""
{SYSTEM_PROMPT}

User question:
{question}

Answer the question directly.
""".strip()

    question_text = question.get("question", "")
    domain = question.get("domain", "")

    # --------------------------------------------------------
    # Q-COMMERCE
    # --------------------------------------------------------

    if domain == "qcommerce":

        review_title = str(
            question.get("review_title") or ""
        ).strip()

        review_context = str(
            question.get("review_context") or ""
        ).strip()

        if not review_context:
            raise ValueError(
                "Q-Commerce question is missing review_context."
            )

        return f"""
{SYSTEM_PROMPT}

Customer review title:
{review_title or "Not provided"}

Original customer review:
{review_context}

Question:
{question_text}

Instructions:
- Answer using only the supplied customer review as evidence.
- Clearly distinguish customer reports from independently verified facts.
- Do not invent product facts.
- Do not assume an objective defect based only on a customer complaint.
- If the review does not establish the answer, say so.
""".strip()

    # --------------------------------------------------------
    # CINEMA
    # --------------------------------------------------------

    if domain == "cinema":

        subject = str(question.get("subject") or "").strip()
        movie_title = lookup_cinema_title(subject) if subject else None

        if movie_title and subject:
            question_text = question_text.replace(subject, movie_title)

        question_type = str(
            question.get("question_type") or ""
        ).strip().lower()

        context = question.get("context") or {}

        if question_type == "ambiguous":

            candidates = context.get("candidate_films", [])
            candidate_lines = []

            for item in candidates:
                title = item.get("title", "Unknown title")
                year = item.get("year", "Unknown year")
                title_type = item.get("title_type", "unknown type")

                candidate_lines.append(
                    f"- {title} ({year}; {title_type})"
                )

            candidate_text = "\n".join(candidate_lines)

            return f"""
{SYSTEM_PROMPT}

Cinema question:
{question_text}

The supplied source contains multiple records with this same title.

Matching candidate records:
{candidate_text or "Multiple matching records exist."}

Do not choose one candidate arbitrarily.
Explain that the title is ambiguous and ask which film the user means.
""".strip()

        if question_type == "unsupported_evidence":

            return f"""
{SYSTEM_PROMPT}

Cinema question:
{question_text}

The supplied IMDb source contains these tables:
- Titles
- Ratings
- Crew
- Cast members
- People
- Indian alternate titles

The supplied source does not contain an awards table or award records.

Answer only what can be established from this source.
Explicitly state when the requested information cannot be established
from the dataset. Do not invent awards or use outside knowledge.
""".strip()

        return f"""
{SYSTEM_PROMPT}

Cinema question:
{question_text}

Answer from your knowledge. If you do not know the film or cannot
verify the requested detail, say so rather than guessing.

Do not invent cast, credits, ratings, release dates, or alternate titles.
""".strip()

    # --------------------------------------------------------
    # SCIENTISTS
    # --------------------------------------------------------

    if domain == "scientists":

        question_type = str(
            question.get("question_type") or ""
        ).strip().lower()

        evidence = str(
            question.get("evidence") or ""
        ).strip()

        source = str(
            question.get("source") or "collected scientist metadata"
        ).strip()

        source_url = str(
            question.get("source_url") or ""
        ).strip()

        source_line = (
            f"Source: {source}"
            + (f" ({source_url})" if source_url else "")
        )

        # Ambiguous scientist names
        if question_type == "ambiguous":

            candidates = question.get("candidate_subjects") or []
            candidate_lines = []

            for item in candidates:
                if isinstance(item, dict):
                    details = "; ".join(
                        f"{key}: {value}"
                        for key, value in item.items()
                        if value
                    )
                    candidate_lines.append("- " + details)

            return f"""
{SYSTEM_PROMPT}

Scientists benchmark question:
{question_text}

Multiple scientist records share this name.

Candidate records:
{chr(10).join(candidate_lines) or "Multiple matching records exist."}

Do not guess. Explain the ambiguity and ask for a distinguishing
identifier, affiliation, research area, or other context.
""".strip()

        # Unsupported evidence
        if question_type == "unsupported_evidence":

            return f"""
{SYSTEM_PROMPT}

Scientists benchmark question:
{question_text}

{source_line}

Available source evidence:
{evidence or "No additional source excerpt is supplied."}

Answer only from the supplied collected metadata.
The requested information is not established by these sources.

Explicitly state this limitation.
Do not guess or invent facts.
""".strip()

        # False premise
        if question_type == "false_premise":

            return f"""
{SYSTEM_PROMPT}

Scientists benchmark question:
{question_text}

Source evidence:
{evidence}

{source_line}

Check the premise against the source evidence.

If the Nobel award year in the question is incorrect, reject it
and state the correct recorded year.

Do not simply agree with the question's premise.
""".strip()

        # Normal factual question
        return f"""
{SYSTEM_PROMPT}

Scientists benchmark question:
{question_text}

Source evidence:
{evidence}

{source_line}

Answer using the available source evidence.

Do not invent biographical details, publications, affiliations,
awards, citation statistics, or research claims.

If the evidence is insufficient, say so.
""".strip()

    # --------------------------------------------------------
    # CRM
    # --------------------------------------------------------

    if domain == "crm":

        context = question.get("context") or {}

        customer_messages = context.get(
            "customer_messages", []
        )

        company_messages = context.get(
            "company_messages", []
        )

        question_type = question.get("question_type")

        if question_type in (
            "customer_report",
            "evidence_retrieval"
        ) and not customer_messages:

            raise ValueError(
                "CRM question is missing customer conversation context."
            )

        if question_type == "company_response_context":

            if not company_messages:

                return f"""
{SYSTEM_PROMPT}

The supplied conversation contains no company response.

Question:
{question_text}

Answer that no company response is present in the supplied
conversation. Do not assume that the issue was resolved.
""".strip()

        customer_text = "\n".join(
            f"- {message}" for message in customer_messages
        ) or "No customer messages provided."

        company_text = "\n".join(
            f"- {message}" for message in company_messages
        ) or "No company messages provided."

        return f"""
{SYSTEM_PROMPT}

CRM conversation context:

Customer messages:
{customer_text}

Company messages:
{company_text}

Question:
{question_text}

Instructions:
- Answer using only the supplied conversation.
- Distinguish customer statements from company statements.
- Do not invent missing details.
- Do not assume a complaint was resolved just because the company replied.
- If the conversation does not establish an answer, explain that.
""".strip()

    # --------------------------------------------------------
    # OTHER DOMAINS
    # --------------------------------------------------------

    return f"""
{SYSTEM_PROMPT}

User question:
{question_text}

Answer the question directly.
""".strip()


# ============================================================
# RESPONSE FILE HELPERS
# ============================================================

def response_file(provider):
    return RESPONSES_DIR / f"{provider}.jsonl"


def load_completed_ids(provider, output_path=None):
    """Load successful question IDs to support resuming."""

    path = Path(output_path) if output_path else response_file(provider)
    completed = set()

    if not path.exists():
        return completed

    with open(path, "r", encoding="utf-8") as file:
        for line in file:

            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

                if record.get("status") == "success":
                    question_id = record.get("question_id")

                    if question_id:
                        completed.add(question_id)

            except json.JSONDecodeError:
                continue

    return completed


def save_record(provider, record, output_path=None):

    path = Path(output_path) if output_path else response_file(provider)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as file:
        file.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )


def make_record(
    question,
    provider,
    model,
    answer=None,
    status="success",
    latency_seconds=None,
    usage=None,
    error=None,
):

    return {
        "question_id": question["question_id"],
        "ground_truth_id": question.get("ground_truth_id"),
        "domain": question["domain"],
        "question": question["question"],
        "question_type": question.get("question_type"),
        "category": question.get("category"),
        "attribute": question.get("attribute"),
        "conversation_id": question.get("conversation_id"),
        "hallucination_target": question.get("hallucination_target"),
        "provider": provider,
        "model": model,
        "answer": answer,
        "status": status,
        "latency_seconds": latency_seconds,
        "usage": usage,
        "error": error,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# USAGE EXTRACTION
# ============================================================

def extract_openai_usage(response):

    usage = getattr(response, "usage", None)

    if usage is None:
        return None

    result = {}

    for field in [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
    ]:

        value = getattr(usage, field, None)

        if value is not None:
            result[field] = value

    return result or None


# ============================================================
# RETRY AND ERROR HANDLING
# ============================================================

class DailyQuotaExhausted(RuntimeError):
    """Raised when a provider reports exhausted daily/account quota."""


def is_daily_quota_error(error):

    message = str(error).lower()

    temporary_markers = (
        "per minute",
        "per_minute",
        "requests per minute",
        "tokens per minute",
        "retry_delay",
        "retry in",
    )

    if any(marker in message for marker in temporary_markers):
        return False

    hard_quota_markers = (
        "per day",
        "per_day",
        "requests_per_day",
        "daily quota",
        "quota exceeded",
        "exceeded your current quota",
        "current quota",
        "check your plan and billing details",
    )

    return any(marker in message for marker in hard_quota_markers)


def is_retryable_error(error):

    message = str(error).lower()
    status_code = getattr(error, "status_code", None)

    if status_code in (429, 500, 502, 503, 504):
        return True

    temporary_markers = (
        "503",
        "unavailable",
        "resource_exhausted",
        "429",
        "rate limit",
        "too many requests",
        "temporarily overloaded",
        "high demand",
        "500 internal",
        "502",
        "504",
    )

    return any(marker in message for marker in temporary_markers)


def call_with_retry(function, max_retries=4):

    last_error = None

    for attempt in range(max_retries):

        try:
            return function()

        except Exception as error:

            last_error = error

            if is_daily_quota_error(error):
                raise DailyQuotaExhausted(str(error)) from error

            if not is_retryable_error(error) or attempt == max_retries - 1:
                raise

            message = str(error).lower()

            if (
                "429" in message
                or "resource_exhausted" in message
                or "rate limit" in message
            ):
                wait_time = min(20 * (2 ** attempt), 120)
            else:
                wait_time = min(10 * (2 ** attempt), 120)

            print(
                f"    Temporary API error. Retry "
                f"{attempt + 1}/{max_retries - 1} "
                f"in {wait_time}s: {str(error)[:180]}"
            )

            time.sleep(wait_time)

    raise last_error


# ============================================================
# OPENAI-COMPATIBLE PROVIDERS
# ============================================================

def call_openai_compatible(
    provider,
    api_key,
    model,
    base_url,
    question,
):

    from openai import OpenAI

    client_kwargs = {
        "api_key": api_key,
    }

    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    prompt = build_prompt(question)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        max_tokens=1000,
    )

    answer = response.choices[0].message.content
    usage = extract_openai_usage(response)

    return answer, usage


# ============================================================
# GEMINI
# ============================================================

def call_gemini(api_key, model, question):

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = build_prompt(question)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=1000,
        ),
    )

    answer = response.text or ""
    usage = None

    metadata = getattr(response, "usage_metadata", None)

    if metadata is not None:

        usage = {}

        for source_name, output_name in [
            ("prompt_token_count", "prompt_tokens"),
            ("candidates_token_count", "completion_tokens"),
            ("total_token_count", "total_tokens"),
        ]:

            value = getattr(metadata, source_name, None)

            if value is not None:
                usage[output_name] = value

        if not usage:
            usage = None

    return answer, usage


# ============================================================
# CLAUDE
# ============================================================

def call_claude(api_key, model, question):

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": build_prompt(question),
            }
        ],
    )

    answer_parts = []

    for block in response.content:
        if getattr(block, "type", None) == "text":
            answer_parts.append(block.text)

    answer = "\n".join(answer_parts).strip()
    usage = None

    response_usage = getattr(response, "usage", None)

    if response_usage is not None:

        usage = {}

        input_tokens = getattr(
            response_usage,
            "input_tokens",
            None,
        )

        output_tokens = getattr(
            response_usage,
            "output_tokens",
            None,
        )

        if input_tokens is not None:
            usage["prompt_tokens"] = input_tokens

        if output_tokens is not None:
            usage["completion_tokens"] = output_tokens

        if input_tokens is not None and output_tokens is not None:
            usage["total_tokens"] = input_tokens + output_tokens

        if not usage:
            usage = None

    return answer, usage


# ============================================================
# PROVIDER DISPATCH
# ============================================================

def call_model(
    provider,
    api_key,
    model,
    base_url,
    question,
):

    if provider == "gemini":
        return call_gemini(
            api_key=api_key,
            model=model,
            question=question,
        )

    if provider == "claude":
        return call_claude(
            api_key=api_key,
            model=model,
            question=question,
        )

    if provider in ("openai", "grok", "deepseek", "qwen"):
        return call_openai_compatible(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            question=question,
        )

    raise ValueError(f"Unknown provider: {provider}")


# ============================================================
# RUN ONE PROVIDER
# ============================================================

def run_provider(
    provider,
    questions,
    limit=None,
    offset=0,
    request_delay=None,
    output_path=None,
):

    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Choose from: {', '.join(PROVIDERS)}"
        )

    config = PROVIDERS[provider]

    api_key = os.getenv(config["key_env"])
    model = os.getenv(config["model_env"])

    base_url = None

    if "base_url_env" in config:
        base_url = os.getenv(config["base_url_env"])

    if not api_key:
        raise RuntimeError(
            f"{config['key_env']} is missing from .env"
        )

    if not model:
        raise RuntimeError(
            f"{config['model_env']} is missing from .env"
        )

    output_path = (
        Path(output_path)
        if output_path
        else response_file(provider)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    completed_ids = load_completed_ids(provider, output_path)

    selected_questions = questions[offset:]

    if limit is not None:
        selected_questions = selected_questions[:limit]

    print()
    print("=" * 70)
    print(f"PROVIDER:  {provider.upper()}")
    print(f"MODEL:     {model}")
    print(f"QUESTIONS: {len(selected_questions)}")
    print(f"COMPLETED: {len(completed_ids)}")
    print(f"OUTPUT:    {output_path}")
    print("=" * 70)

    success_count = 0
    error_count = 0
    skipped_count = 0
    quota_exhausted = False

    if request_delay is None:

        if provider == "gemini":
            request_delay = float(
                os.getenv("GEMINI_REQUEST_INTERVAL_SECONDS", "15")
            )
        else:
            request_delay = float(
                os.getenv("REQUEST_INTERVAL_SECONDS", "0")
            )

    if request_delay < 0:
        raise ValueError("Request delay cannot be negative.")

    last_request_started = None

    for index, question in enumerate(selected_questions, start=1):

        question_id = question["question_id"]

        if question_id in completed_ids:

            skipped_count += 1

            print(
                f"[{index}/{len(selected_questions)}] "
                f"{question_id} -> already completed"
            )

            continue

        print(
            f"[{index}/{len(selected_questions)}] "
            f"{question_id}: "
            f"{question['question'][:80]}"
        )

        # Respect request spacing.
        if last_request_started is not None and request_delay > 0:

            elapsed = time.monotonic() - last_request_started
            remaining = request_delay - elapsed

            if remaining > 0:
                print(
                    f"    Waiting {remaining:.1f}s "
                    "to respect request pacing..."
                )
                time.sleep(remaining)

        start_time = time.perf_counter()
        last_request_started = time.monotonic()

        try:

            answer, usage = call_with_retry(
                lambda: call_model(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                    question=question,
                )
            )

            latency = time.perf_counter() - start_time

            record = make_record(
                question=question,
                provider=provider,
                model=model,
                answer=answer,
                status="success",
                latency_seconds=round(latency, 4),
                usage=usage,
            )

            save_record(provider, record, output_path)
            success_count += 1

            print(
                f"    SUCCESS | {latency:.2f}s | "
                f"{(answer or '')[:120].replace(chr(10), ' ')}"
            )

        except DailyQuotaExhausted as error:

            latency = time.perf_counter() - start_time

            record = make_record(
                question=question,
                provider=provider,
                model=model,
                answer=None,
                status="error",
                latency_seconds=round(latency, 4),
                error=f"DAILY_QUOTA_EXHAUSTED: {error}",
            )

            save_record(provider, record, output_path)
            error_count += 1
            quota_exhausted = True

            print(
                "    DAILY QUOTA EXHAUSTED. "
                "Stopping this provider to avoid wasted requests."
            )

            break

        except Exception as error:

            latency = time.perf_counter() - start_time

            record = make_record(
                question=question,
                provider=provider,
                model=model,
                answer=None,
                status="error",
                latency_seconds=round(latency, 4),
                error=str(error),
            )

            save_record(provider, record, output_path)
            error_count += 1

            print(
                f"    ERROR | {type(error).__name__}: "
                f"{str(error)[:200]}"
            )

    print()
    print("-" * 70)
    print(f"{provider.upper()} FINISHED")
    print(f"Successful: {success_count}")
    print(f"Errors:     {error_count}")
    print(f"Skipped:    {skipped_count}")

    if quota_exhausted:
        print("Stopped:    daily/account quota exhausted")

    print(f"Request delay: {request_delay:g}s")
    print(f"Output:        {output_path}")
    print("-" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="HalluBench multi-model response collector"
    )

    parser.add_argument(
        "--domain",
        type=str,
        choices=list(DOMAIN_QUESTION_FILES.keys()),
        default="cricket",
        help="Benchmark domain to run",
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=list(PROVIDERS.keys()) + ["all"],
        default="all",
        help="Provider to run",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of questions to run",
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Starting question index",
    )

    parser.add_argument(
        "--questions-file",
        type=str,
        default=None,
        help=(
            "Optional custom questions file. "
            "If omitted, the file for --domain is used."
        ),
    )

    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help=(
            "Optional experiment name to keep response files separate, "
            "for example pilot100."
        ),
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=None,
        help="Minimum seconds between request starts. Gemini defaults to 15.",
    )

    args = parser.parse_args()

    # Select question file automatically from domain.
    if args.questions_file:
        questions_file = Path(args.questions_file)

        if not questions_file.is_absolute():
            questions_file = ROOT / questions_file

    else:
        questions_file = DOMAIN_QUESTION_FILES[args.domain]

    print()
    print("HalluBench Model Response Collector")
    print("=" * 70)
    print(f"Domain:         {args.domain}")
    print(f"Questions file: {questions_file}")
    print(f"Output folder:  {RESPONSES_DIR}")
    print()

    questions = load_questions(questions_file)

    print(f"Loaded {len(questions):,} questions.")

    # Validate that questions belong to the selected domain.
    wrong_domain = [
        question.get("question_id")
        for question in questions
        if question.get("domain") != args.domain
    ]

    if wrong_domain:
        raise ValueError(
            f"Found {len(wrong_domain)} questions whose domain does not "
            f"match --domain {args.domain}. "
            f"Example question IDs: {wrong_domain[:5]}"
        )

    if args.offset < 0:
        raise ValueError("--offset cannot be negative.")

    if args.limit is not None and args.limit < 0:
        raise ValueError("--limit cannot be negative.")

    if args.provider == "all":
        providers = list(PROVIDERS.keys())
    else:
        providers = [args.provider]

    for provider in providers:

        if args.run_name:
            output_filename = f"{provider}_{args.run_name}.jsonl"
        else:
            output_filename = f"{provider}.jsonl"

        output_path = RESPONSES_DIR / output_filename

        try:

            run_provider(
                provider=provider,
                questions=questions,
                limit=args.limit,
                offset=args.offset,
                request_delay=args.request_delay,
                output_path=output_path,
            )

        except KeyboardInterrupt:

            print(
                "\nCollection interrupted by user. "
                "Successful responses are preserved."
            )

            break

        except Exception as error:

            print()
            print(f"FAILED PROVIDER: {provider}")
            print(f"{type(error).__name__}: {error}")
            print()

    print()
    print("=" * 70)
    print("MODEL COLLECTION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()