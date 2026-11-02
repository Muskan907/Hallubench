import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path("data/raw/qcommerce/olist")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATASET = "olistbr/brazilian-ecommerce"

EXPECTED_FILES = [
    "olist_orders_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_products_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv"
]

def main():
    existing = [
        name for name in EXPECTED_FILES
        if (OUTPUT_DIR / name).exists()
    ]

    if len(existing) == len(EXPECTED_FILES):
        print("[SKIP] All Olist CSV files already exist.")
        return

    print("Starting Olist dataset download...")
    print(f"Destination: {OUTPUT_DIR}")

    command = [
        sys.executable, "-m", "kaggle",
        "datasets", "download",
        "-d", DATASET,
        "-p", str(OUTPUT_DIR),
        "--unzip"
    ]

    try:
        result = subprocess.run(command, check=False)

        if result.returncode != 0:
            print("\n[ERROR] Kaggle download failed.")
            print("Check that Kaggle CLI is installed and your Kaggle API credentials are configured.")
            print("You can also download the ZIP manually from:")
            print("https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
            return

        print("\nChecking downloaded files...")
        missing = []

        for name in EXPECTED_FILES:
            if (OUTPUT_DIR / name).exists():
                print(f"[OK] {name}")
            else:
                missing.append(name)
                print(f"[MISSING] {name}")

        if missing:
            print("\nSome expected files were not found. Check the extracted folder.")
        else:
            print("\n[SUCCESS] All Olist CSV files are available.")

    except FileNotFoundError:
        print("[ERROR] Kaggle CLI not found.")
        print("Install it with: python -m pip install -U kaggle")

if __name__ == "__main__":
    main()
