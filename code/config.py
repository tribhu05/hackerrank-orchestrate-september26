"""
Configuration and constants for Buy or Wait financial decision agent.
"""
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
MEDIA_IMAGES_DIR = DATASET_DIR / "media" / "images"
OUTPUT_CSV_PATH = REPO_ROOT / "output.csv"
LOG_FILE_PATH = REPO_ROOT / "log.txt"

# Dataset Files
REQUESTS_CSV = DATASET_DIR / "requests.csv"
SAMPLE_REQUESTS_CSV = DATASET_DIR / "sample_requests.csv"
FINANCIAL_PROFILES_CSV = DATASET_DIR / "financial_profiles.csv"
FINANCIAL_EVENTS_CSV = DATASET_DIR / "financial_events.csv"
EXCHANGE_RATES_CSV = DATASET_DIR / "exchange_rates.csv"
REQUEST_PAYMENT_OPTIONS_CSV = DATASET_DIR / "request_payment_options.csv"
MESSAGES_CSV = DATASET_DIR / "messages.csv"
IMAGES_CSV = DATASET_DIR / "images.csv"

# Allowed Enum Values
ALLOWED_AFFORDABILITY_STATUS = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}

ALLOWED_PAYMENT_METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}

# Supported Currencies
SUPPORTED_CURRENCIES = {"INR", "EUR", "IDR", "ZAR", "USD"}

# Simulation Parameters
FORECAST_DAYS = 90
MAX_SPENDING_CHANGES = 3
