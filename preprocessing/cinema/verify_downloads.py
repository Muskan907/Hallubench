import gzip
from pathlib import Path

folder = Path("data/raw/cinema")
files = sorted(folder.glob("*.gz"))

for path in files:
    print(f"\nChecking {path.name}...")
    total_bytes = 0

    try:
        with gzip.open(path, "rb") as f:
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)

        print(f"VALID | Compressed: {path.stat().st_size / 1048576:.2f} MB")
        print(f"Uncompressed: {total_bytes / 1048576:.2f} MB")

    except Exception as e:
        print(f"INVALID | {e}")
