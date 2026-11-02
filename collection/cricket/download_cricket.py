from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import requests


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "cricket"

RAW_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Cricsheet source
# ---------------------------------------------------------

SOURCE_URL = "https://cricsheet.org/downloads/odis_json.zip"

OUTPUT_FILE = RAW_DIR / "odis_json.zip"


# ---------------------------------------------------------
# Download function
# ---------------------------------------------------------

def download_dataset():
    print("=" * 60)
    print("HalluBench - Cricket Data Collection")
    print("=" * 60)

    print("\nSource:")
    print(SOURCE_URL)

    print("\nDownloading...")

    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": "HalluBench/1.0 research benchmark"
        },
        timeout=120
    )

    response.raise_for_status()

    OUTPUT_FILE.write_bytes(response.content)

    print("\nDownload completed.")
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"File size: {len(response.content):,} bytes")


# ---------------------------------------------------------
# SHA-256 checksum
# ---------------------------------------------------------

def calculate_checksum():

    sha256 = hashlib.sha256()

    with OUTPUT_FILE.open("rb") as file:

        while True:

            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ---------------------------------------------------------
# Save dataset metadata
# ---------------------------------------------------------

def save_metadata(checksum):

    metadata = {
        "dataset": "Cricsheet ODI JSON",
        "source": "Cricsheet",
        "source_url": SOURCE_URL,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "file": str(OUTPUT_FILE.relative_to(PROJECT_ROOT)),
        "sha256": checksum
    }

    metadata_file = RAW_DIR / "metadata.json"

    metadata_file.write_text(
        json.dumps(
            metadata,
            indent=4
        ),
        encoding="utf-8"
    )

    print("\nMetadata saved to:")
    print(metadata_file)


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    download_dataset()

    checksum = calculate_checksum()

    print("\nSHA-256:")
    print(checksum)

    save_metadata(checksum)

    print("\n" + "=" * 60)
    print("Cricket data collection completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()