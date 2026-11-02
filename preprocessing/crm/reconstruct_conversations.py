import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data/processed/crm/messages.jsonl"
OUTPUT_DIR = ROOT / "data/processed/crm"

DB_FILE = OUTPUT_DIR / "conversation_index.sqlite"
OUTPUT_FILE = OUTPUT_DIR / "conversations.jsonl"
MANIFEST_FILE = OUTPUT_DIR / "conversation_manifest.json"

BATCH_SIZE = 10000


def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Start with a fresh index for reproducible results.
    if DB_FILE.exists():
        DB_FILE.unlink()

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("PRAGMA cache_size=-100000")

    print("=" * 65)
    print("HALLUBENCH | CRM CONVERSATION RECONSTRUCTION")
    print("=" * 65)

    # --------------------------------------------------
    # 1. CREATE DATABASE TABLE
    # --------------------------------------------------

    conn.execute("""
        CREATE TABLE messages (
            message_id TEXT PRIMARY KEY,
            author_id TEXT,
            direction TEXT,
            created_at TEXT,
            text TEXT,
            parent_id TEXT,
            root_id TEXT
        )
    """)

    print("\nLoading parsed messages into SQLite...")

    batch = []
    total = 0

    with INPUT_FILE.open("r", encoding="utf-8") as file:

        for line in file:

            if not line.strip():
                continue

            record = json.loads(line)

            message_id = record["message_id"]
            parent_id = record.get("parent_message_id")

            batch.append((
                message_id,
                record.get("author_id"),
                record.get("direction"),
                record.get("created_at_utc"),
                record.get("text", ""),
                parent_id,
                message_id
            ))

            if len(batch) >= BATCH_SIZE:

                conn.executemany("""
                    INSERT INTO messages
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batch)

                total += len(batch)
                batch.clear()

                conn.commit()

                print(f"Loaded {total:,} messages...")

    if batch:
        conn.executemany("""
            INSERT INTO messages
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, batch)

        total += len(batch)
        conn.commit()

    print(f"\nTotal messages indexed: {total:,}")

    # --------------------------------------------------
    # 2. CREATE INDEXES
    # --------------------------------------------------

    print("\nCreating database indexes...")

    conn.execute("""
        CREATE INDEX idx_parent
        ON messages(parent_id)
    """)

    conn.execute("""
        CREATE INDEX idx_root
        ON messages(root_id)
    """)

    conn.execute("""
        CREATE INDEX idx_timestamp
        ON messages(created_at)
    """)

    conn.commit()

    # --------------------------------------------------
    # 3. IDENTIFY ROOT MESSAGES
    # --------------------------------------------------

    print("\nIdentifying conversation roots...")

    # Start with every message unassigned.
    conn.execute("""
        UPDATE messages
        SET root_id = NULL
    """)

    # A message is a root if it has no parent or its
    # parent does not exist in the downloaded dataset.

    conn.execute("""
        UPDATE messages
        SET root_id = message_id
        WHERE parent_id IS NULL
           OR NOT EXISTS (
               SELECT 1
               FROM messages p
               WHERE p.message_id = messages.parent_id
           )
    """)

    conn.commit()

    # --------------------------------------------------
    # 4. PROPAGATE ROOT IDS SAFELY
    # --------------------------------------------------

    print("\nConnecting conversation threads...")

    iteration = 0
    total_assigned = 0

    while True:

        conn.execute("""
            UPDATE messages AS m
            SET root_id = (
                SELECT p.root_id
                FROM messages p
                WHERE p.message_id = m.parent_id
            )
            WHERE m.root_id IS NULL
              AND m.parent_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM messages p
                  WHERE p.message_id = m.parent_id
                    AND p.root_id IS NOT NULL
              )
        """)

        changed = conn.execute(
            "SELECT changes()"
        ).fetchone()[0]

        conn.commit()

        iteration += 1
        total_assigned += changed

        if iteration % 10 == 0 or changed == 0:

            print(
                f"Pass {iteration}: "
                f"{changed:,} messages assigned"
            )

        if changed == 0:
            break

    print(f"Propagation completed in {iteration} passes.")
    print(f"Messages connected: {total_assigned:,}")

    # --------------------------------------------------
    # 4B. HANDLE UNRESOLVED COMPONENTS SAFELY
    # --------------------------------------------------

    unresolved = conn.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE root_id IS NULL
    """).fetchone()[0]

    print(
        f"Messages in unresolved components: {unresolved:,}"
    )

    # Do not invent links for cyclic or disconnected
    # components. Keep each unresolved message separate.

    if unresolved:

        conn.execute("""
            UPDATE messages
            SET root_id = message_id
            WHERE root_id IS NULL
        """)

        conn.commit()

    print("All messages now have a conversation ID.")
    # --------------------------------------------------
    # 5. CHECK UNRESOLVED LINKS
    # --------------------------------------------------

    unresolved = conn.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE root_id IS NULL
    """).fetchone()[0]

    if unresolved:
        raise RuntimeError(
            f"{unresolved:,} messages have unresolved conversation roots."
        )

    # --------------------------------------------------
    # 6. CALCULATE CONVERSATION STATISTICS
    # --------------------------------------------------

    print("\nCalculating conversation statistics...")

    conversation_count = conn.execute("""
        SELECT COUNT(DISTINCT root_id)
        FROM messages
    """).fetchone()[0]

    grouped = conn.execute("""
        SELECT
            COUNT(*) AS message_count,
            SUM(CASE WHEN direction = 'customer' THEN 1 ELSE 0 END),
            SUM(CASE WHEN direction = 'company' THEN 1 ELSE 0 END)
        FROM messages
        GROUP BY root_id
    """)

    single_message_threads = 0
    multi_message_threads = 0
    max_thread_size = 0

    for row in grouped:

        count = row[0]

        if count == 1:
            single_message_threads += 1
        else:
            multi_message_threads += 1

        max_thread_size = max(max_thread_size, count)

    # --------------------------------------------------
    # 7. EXPORT CONVERSATIONS AS JSONL
    # --------------------------------------------------

    print("\nExporting reconstructed conversations...")

    cursor = conn.execute("""
        SELECT
            root_id,
            message_id,
            author_id,
            direction,
            created_at,
            text,
            parent_id
        FROM messages
        ORDER BY root_id, created_at, message_id
    """)

    exported = 0
    current_root = None
    conversation_messages = []

    def write_conversation(target, root_id, messages):

        conversation = {
            "conversation_id": root_id,
            "domain": "crm",
            "source_dataset": "customer_support_on_twitter",
            "message_count": len(messages),
            "customer_message_count": sum(
                m["direction"] == "customer" for m in messages
            ),
            "company_message_count": sum(
                m["direction"] == "company" for m in messages
            ),
            "messages": messages
        }

        target.write(
            json.dumps(
                conversation,
                ensure_ascii=False,
                separators=(",", ":")
            ) + "\n"
        )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline="\n"
    ) as target:

        for row in cursor:

            root_id = row[0]

            if current_root is not None and root_id != current_root:

                write_conversation(
                    target,
                    current_root,
                    conversation_messages
                )

                exported += 1
                conversation_messages = []

                if exported % 100000 == 0:
                    print(
                        f"Exported {exported:,} conversations..."
                    )

            current_root = root_id

            conversation_messages.append({
                "message_id": row[1],
                "author_id": row[2],
                "direction": row[3],
                "created_at_utc": row[4],
                "text": row[5],
                "parent_message_id": row[6]
            })

        if current_root is not None:

            write_conversation(
                target,
                current_root,
                conversation_messages
            )

            exported += 1

    # --------------------------------------------------
    # 8. CREATE MANIFEST
    # --------------------------------------------------

    manifest = {
        "domain": "crm",
        "source_dataset": "customer_support_on_twitter",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(INPUT_FILE.relative_to(ROOT)),
        "database_file": str(DB_FILE.relative_to(ROOT)),
        "output_file": str(OUTPUT_FILE.relative_to(ROOT)),
        "total_messages": total,
        "total_conversations": conversation_count,
        "single_message_conversations": single_message_threads,
        "multi_message_conversations": multi_message_threads,
        "maximum_messages_in_conversation": max_thread_size,
        "root_propagation_passes": iteration,
        "unresolved_messages": unresolved,
        "reconstruction_method": (
            "Parent-child links using in_response_to_tweet_id. "
            "Missing-parent messages become independent roots."
        ),
        "notes": [
            "Original source messages remain unchanged.",
            "Messages are ordered by timestamp and message ID.",
            "Conversation IDs are the root message IDs.",
            "A connected thread does not prove that a complaint was resolved.",
            "Missing parent references are not treated as verified links."
        ],
        "unresolved_components_before_fallback": unresolved,

        "unresolved_handling": (
            "Unresolved messages were assigned individual conversation IDs "
            "to avoid inventing connections."
        )
    }

    MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    conn.close()

    print("\n" + "=" * 65)
    print("CRM CONVERSATION RECONSTRUCTION COMPLETED")
    print("=" * 65)

    print(f"Total messages: {total:,}")
    print(f"Total conversations: {conversation_count:,}")
    print(f"Single-message conversations: {single_message_threads:,}")
    print(f"Multi-message conversations: {multi_message_threads:,}")
    print(f"Largest conversation: {max_thread_size:,} messages")
    print(f"Unresolved messages: {unresolved:,}")
    print(f"Propagation passes: {iteration}")

    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Database: {DB_FILE}")
    print(f"Manifest: {MANIFEST_FILE}")


if __name__ == "__main__":

    try:
        main()

    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")
        sys.exit(1)
