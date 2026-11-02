"""
Download the Customer Support on Twitter dataset from Kaggle.

Source:
https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter

Run from the HalluBench project root:
    python collection/crm/download_twitter_support.py

Optional:
    python collection/crm/download_twitter_support.py --force
"""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "crm"
DATASET_SLUG = "thoughtvector/customer-support-on-twitter"
SOURCE_URL = "https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter"
ZIP_PATH = RAW_DIR / "customer-support-on-twitter.zip"
CSV_PATH = RAW_DIR / "twcs.csv"
MANIFEST_PATH = RAW_DIR / "download_manifest.json"

EXPECTED_COLUMNS = {
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "response_tweet_id",
    "in_response_to_tweet_id",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(force: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if ZIP_PATH.exists() and not force:
        print(f"Existing archive found: {ZIP_PATH}")
        print("Skipping download. Use --force to download it again.")
        return

    kaggle_executable = shutil.which("kaggle")
    if not kaggle_executable:
        raise RuntimeError(
            "Kaggle CLI was not found. Install it with:\n"
            "    python -m pip install kaggle\n"
            "Then configure Kaggle API credentials and retry."
        )

    command = [
        kaggle_executable,
        "datasets",
        "download",
        "-d",
        DATASET_SLUG,
        "-p",
        str(RAW_DIR),
        "--force",
    ]

    print("\nDownloading Customer Support on Twitter from Kaggle...")
    print("This dataset is approximately 0.5 GB. The download may take a while.\n")

    subprocess.run(command, check=True)

    # Kaggle normally names the archive after the dataset slug.
    if not ZIP_PATH.exists():
        candidates = sorted(RAW_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise FileNotFoundError(
                f"Kaggle download finished, but no ZIP archive was found in {RAW_DIR}"
            )
        newest = candidates[0]
        if newest != ZIP_PATH:
            newest.replace(ZIP_PATH)


def extract_dataset(force: bool = False) -> None:
    if CSV_PATH.exists() and not force:
        print(f"\nExisting CSV found: {CSV_PATH}")
        print("Skipping extraction. Use --force to extract again.")
        return

    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Dataset ZIP not found: {ZIP_PATH}")

    print("\nChecking ZIP contents...")
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        members = [
            name for name in archive.namelist()
            if Path(name).name.lower() == "twcs.csv"
        ]

        if not members:
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            raise FileNotFoundError(
                "Could not find twcs.csv in the downloaded archive. "
                f"CSV files found: {csv_members[:20]}"
            )

        # Select the exact expected source file, not an arbitrary CSV.
        member = members[0]
        print(f"Extracting: {member}")

        # Stream to the destination instead of extracting arbitrary archive paths.
        with archive.open(member, "r") as source, CSV_PATH.open("wb") as target:
            shutil.copyfileobj(source, target)

    print(f"Extracted original CSV to: {CSV_PATH}")


def inspect_csv() -> dict:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Expected CSV not found: {CSV_PATH}")

    print("\nValidating CSV schema and counting records...")
    row_count = 0
    inbound_true = 0
    inbound_false = 0
    empty_text = 0
    min_created_at = None
    max_created_at = None

    # utf-8-sig safely handles an optional UTF-8 BOM.
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        actual_columns = set(reader.fieldnames or [])
        missing_columns = sorted(EXPECTED_COLUMNS - actual_columns)

        if missing_columns:
            raise ValueError(
                "Dataset schema validation failed. Missing columns: "
                + ", ".join(missing_columns)
                + f". Found columns: {reader.fieldnames}"
            )

        for row in reader:
            row_count += 1

            inbound_value = (row.get("inbound") or "").strip().lower()
            if inbound_value == "true":
                inbound_true += 1
            elif inbound_value == "false":
                inbound_false += 1

            if not (row.get("text") or "").strip():
                empty_text += 1

            created_at = (row.get("created_at") or "").strip()
            if created_at:
                if min_created_at is None or created_at < min_created_at:
                    min_created_at = created_at
                if max_created_at is None or created_at > max_created_at:
                    max_created_at = created_at

    if row_count == 0:
        raise ValueError("The extracted CSV contains no data rows.")

    print("\nCSV validation passed.")
    print(f"Rows:              {row_count:,}")
    print(f"Customer inbound:  {inbound_true:,}")
    print(f"Company outbound:  {inbound_false:,}")
    print(f"Empty text rows:   {empty_text:,}")
    print(f"Columns:           {', '.join(sorted(actual_columns))}")

    return {
        "row_count": row_count,
        "inbound_customer_messages": inbound_true,
        "outbound_company_messages": inbound_false,
        "empty_text_rows": empty_text,
        "columns": sorted(actual_columns),
        "minimum_created_at_lexical": min_created_at,
        "maximum_created_at_lexical": max_created_at,
    }


def write_manifest(stats: dict) -> None:
    manifest = {
        "dataset_name": "Customer Support on Twitter",
        "dataset_slug": DATASET_SLUG,
        "source_url": SOURCE_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license_as_listed_on_kaggle": "CC BY-NC-SA 4.0",
        "license_note": (
            "Non-commercial ShareAlike license. Review the dataset page and "
            "original rights/terms before redistribution or other use. "
            "The Kaggle dataset page says commercial applications and use "
            "of the full dataset require contacting the dataset creator."
        ),
        "archive_path": str(ZIP_PATH.relative_to(ROOT)),
        "archive_size_bytes": ZIP_PATH.stat().st_size,
        "archive_sha256": sha256_file(ZIP_PATH),
        "csv_path": str(CSV_PATH.relative_to(ROOT)),
        "csv_size_bytes": CSV_PATH.stat().st_size,
        "csv_sha256": sha256_file(CSV_PATH),
        "source_record_unit": "one tweet/message per row",
        "statistics": stats,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nManifest saved: {MANIFEST_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and validate the Customer Support on Twitter dataset."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download the archive again and re-extract the CSV.",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("HALLUBENCH | CRM DATASET COLLECTION")
    print("=" * 68)
    print(f"Project root: {ROOT}")
    print(f"Raw data dir: {RAW_DIR}")
    print(f"Dataset:      {SOURCE_URL}")

    try:
        download_dataset(force=args.force)
        extract_dataset(force=args.force)
        stats = inspect_csv()
        write_manifest(stats)

        print("\n" + "=" * 68)
        print("CRM DATASET DOWNLOAD COMPLETED")
        print("=" * 68)
        print(f"Original ZIP: {ZIP_PATH}")
        print(f"Raw CSV:      {CSV_PATH}")
        print(f"Manifest:     {MANIFEST_PATH}")
        return 0

    except subprocess.CalledProcessError as error:
        print(f"\nKaggle download failed with exit code {error.returncode}.")
        print("Check your Kaggle CLI authentication and dataset access.")
        return 1
    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
