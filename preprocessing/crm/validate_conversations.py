import json
from pathlib import Path

base = Path("data/processed/crm")
file = base / "conversations.jsonl"

print("=" * 65)
print("HALLUBENCH | CRM CONVERSATION VALIDATION")
print("=" * 65)

total = 0
missing_id = 0
empty = 0
bad_messages = 0
single = 0
multi = 0
max_size = 0
sample = None

with file.open("r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad_messages += 1
            continue

        total += 1

        if sample is None:
            sample = obj

        if not obj.get("conversation_id"):
            missing_id += 1

        messages = obj.get("messages", [])

        if not messages:
            empty += 1
        elif len(messages) == 1:
            single += 1
        else:
            multi += 1

        max_size = max(max_size, len(messages))

        for msg in messages:
            if not msg.get("message_id") or not msg.get("text"):
                bad_messages += 1

print("Total conversations:", total)
print("Missing conversation IDs:", missing_id)
print("Empty conversations:", empty)
print("Single-message conversations:", single)
print("Multi-message conversations:", multi)
print("Largest conversation:", max_size)
print("Invalid records/messages:", bad_messages)

if sample:
    print("\nSample conversation keys:", list(sample.keys()))
    print("Sample conversation:")
    print(json.dumps(sample, indent=2, ensure_ascii=False)[:2500])

print("\nValidation completed.")
