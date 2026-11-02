import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data" / "raw" / "crm" / "twcs.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "crm"

OUTPUT_FILE = OUTPUT_DIR / "messages.jsonl"
MANIFEST_FILE = OUTPUT_DIR / "parse_manifest.json"

REQUIRED_COLUMNS = {
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "response_tweet_id",
    "in_response_to_tweet_id"
}


def parse_bool(value):
    value = (value or "").strip().lower()

    if value == "true":
        return True

    if value == "false":
        return False

    raise ValueError(f"Unexpected inbound value: {value}")


def parse_response_ids(value):
    value = (value or "").strip()

    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def parse_timestamp(value):
    value = (value or "").strip()

    if not value:
        return ""

    parsed = datetime.strptime(
        value,
        "%a %b %d %H:%M:%S %z %Y"
    )

    return parsed.astimezone(timezone.utc).isoformat()


def main():

    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stats = Counter()
    direction_counts = Counter()

    timestamp_errors = 0
    malformed_rows = 0

    first_timestamp = None
    last_timestamp = None

    digest = hashlib.sha256()

    print("=" * 65)
    print("HALLUBENCH | CRM MESSAGE PARSING")
    print("=" * 65)

    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as source, open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as target:

        reader = csv.DictReader(source)

        actual_columns = set(reader.fieldnames or [])

        missing = REQUIRED_COLUMNS - actual_columns

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
            )

        for row_number, row in enumerate(reader, start=2):

            try:

                tweet_id = (row.get("tweet_id") or "").strip()
                author_id = (row.get("author_id") or "").strip()

                text = row.get("text") or ""

                inbound = parse_bool(row.get("inbound", ""))

                if not tweet_id:
                    malformed_rows += 1
                    continue

                raw_timestamp = (row.get("created_at") or "").strip()

                try:
                    timestamp_utc = parse_timestamp(raw_timestamp)

                except ValueError:
                    timestamp_utc = ""
                    timestamp_errors += 1

                parent_id = (
                    row.get("in_response_to_tweet_id") or ""
                ).strip()

                response_ids = parse_response_ids(
                    row.get("response_tweet_id", "")
                )

                record = {
                    "message_id": tweet_id,
                    "author_id": author_id,

                    "direction": (
                        "customer" if inbound else "company"
                    ),

                    "inbound": inbound,

                    "created_at_raw": raw_timestamp,
                    "created_at_utc": timestamp_utc,

                    "text": text,

                    "parent_message_id": parent_id or None,
                    "response_message_ids": response_ids,

                    "source_dataset": "customer_support_on_twitter",
                    "source_file": "twcs.csv",
                    "source_row_number": row_number
                }

                serialized = json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(",", ":")
                )

                target.write(serialized + "\n")

                digest.update(
                    (serialized + "\n").encode("utf-8")
                )

                stats["messages_written"] += 1

                direction_counts[record["direction"]] += 1

                stats["messages_with_parent"] += bool(parent_id)

                stats["messages_without_parent"] += not bool(parent_id)

                stats["messages_with_response_ids"] += bool(response_ids)

                stats["messages_without_response_ids"] += not bool(response_ids)

                stats["total_response_ids"] += len(response_ids)

                stats["empty_text"] += not bool(text.strip())

                if timestamp_utc:

                    if (
                        first_timestamp is None
                        or timestamp_utc < first_timestamp
                    ):
                        first_timestamp = timestamp_utc

                    if (
                        last_timestamp is None
                        or timestamp_utc > last_timestamp
                    ):
                        last_timestamp = timestamp_utc

                if stats["messages_written"] % 250000 == 0:

                    print(
                        f"Processed "
                        f"{stats['messages_written']:,} messages..."
                    )

            except Exception as error:

                malformed_rows += 1

                print(
                    f"WARNING: Row {row_number}: "
                    f"{type(error).__name__}: {error}"
                )

    manifest = {

        "source": "Customer Support on Twitter",

        "input_file": str(INPUT_FILE.relative_to(ROOT)),

        "output_file": str(OUTPUT_FILE.relative_to(ROOT)),

        "parsed_at_utc": datetime.now(timezone.utc).isoformat(),

        "messages_written": stats["messages_written"],

        "customer_messages": direction_counts["customer"],

        "company_messages": direction_counts["company"],

        "messages_with_parent": stats["messages_with_parent"],

        "messages_without_parent": stats["messages_without_parent"],

        "messages_with_response_ids": stats["messages_with_response_ids"],

        "messages_without_response_ids": stats["messages_without_response_ids"],

        "total_response_ids": stats["total_response_ids"],

        "empty_text_messages": stats["empty_text"],

        "timestamp_parse_errors": timestamp_errors,

        "malformed_rows_skipped": malformed_rows,

        "earliest_timestamp_utc": first_timestamp,

        "latest_timestamp_utc": last_timestamp,

        "output_sha256": digest.hexdigest(),

        "notes": [
            "Original CSV remains unchanged.",
            "Message IDs are stored as strings.",
            "Response IDs are stored as lists.",
            "Conversation reconstruction is a separate stage."
        ]
    }

    MANIFEST_FILE.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 65)
    print("CRM MESSAGE PARSING COMPLETED")
    print("=" * 65)

    print(
        f"Messages written: "
        f"{stats['messages_written']:,}"
    )

    print(
        f"Customer messages: "
        f"{direction_counts['customer']:,}"
    )

    print(
        f"Company messages: "
        f"{direction_counts['company']:,}"
    )

    print(
        f"Messages with parent: "
        f"{stats['messages_with_parent']:,}"
    )

    print(
        f"Messages with replies: "
        f"{stats['messages_with_response_ids']:,}"
    )

    print(
        f"Total response IDs: "
        f"{stats['total_response_ids']:,}"
    )

    print(f"Timestamp errors: {timestamp_errors:,}")

    print(f"Malformed rows: {malformed_rows:,}")

    print(f"\nOutput: {OUTPUT_FILE}")

    print(f"Manifest: {MANIFEST_FILE}")

    return 0


if __name__ == "__main__":

    try:
        sys.exit(main())

    except Exception as error:

        print(
            f"\nERROR: {type(error).__name__}: {error}"
        )

        sys.exit(1)
