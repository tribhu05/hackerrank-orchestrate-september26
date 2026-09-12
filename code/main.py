"""
Main entry point for Buy or Wait? financial decision agent.
Reads dataset/requests.csv, runs the deterministic financial engine,
and generates the root-level output.csv.
"""
import sys
from pathlib import Path
import time
import pandas as pd

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.config import OUTPUT_CSV_PATH, ALLOWED_AFFORDABILITY_STATUS, ALLOWED_PAYMENT_METHODS
from code.data_loader import DataLoader
from code.decision_engine import DecisionEngine

def validate_predictions(df: pd.DataFrame, expected_count: int = 250) -> list:
    errors = []

    required_cols = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ]

    if list(df.columns) != required_cols:
        errors.append(f"Columns mismatch: got {list(df.columns)}, expected {required_cols}")

    if len(df) != expected_count:
        errors.append(f"Row count mismatch: got {len(df)}, expected {expected_count}")

    if df["request_id"].duplicated().any():
        dups = df[df["request_id"].duplicated()]["request_id"].tolist()
        errors.append(f"Duplicate request IDs found: {dups}")

    for idx, r in df.iterrows():
        rid = r["request_id"]
        status = r["affordability_status"]
        method = r["recommended_payment_method"]
        safe_amt = r["amount_safe_to_pay"]
        earliest_dt = r["earliest_date_for_full_payment"]

        if status not in ALLOWED_AFFORDABILITY_STATUS:
            errors.append(f"[{rid}] Invalid affordability_status: {status}")

        if method not in ALLOWED_PAYMENT_METHODS:
            errors.append(f"[{rid}] Invalid recommended_payment_method: {method}")

        if pd.isna(safe_amt) or safe_amt < 0:
            errors.append(f"[{rid}] Invalid amount_safe_to_pay: {safe_amt}")

        if status == "affordable_now" and pd.isna(earliest_dt):
            errors.append(f"[{rid}] affordable_now must have earliest_date_for_full_payment set")

    return errors

def run():
    start_time = time.time()
    print("=" * 60)
    print("HackerRank Orchestrate — Buy or Wait? Financial Decision Agent")
    print("=" * 60)

    print("\n[1/4] Loading datasets...")
    loader = DataLoader()
    print(f"Loaded {len(loader.profiles)} profiles, {len(loader.requests)} requests, {len(loader.options_by_request)} request options.")

    print("\n[2/4] Initializing Decision Engine...")
    engine = DecisionEngine(loader)

    print(f"\n[3/4] Evaluating {len(loader.requests)} requests...")
    results = []
    for idx, req in enumerate(loader.requests, 1):
        pred = engine.evaluate_request(req)
        results.append(pred)
        if idx % 50 == 0 or idx == len(loader.requests):
            print(f"  Processed {idx}/{len(loader.requests)} requests...")

    df_out = pd.DataFrame(results)

    # Reorder columns explicitly
    cols = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ]
    df_out = df_out[cols]

    print("\n[4/4] Validating outputs...")
    errors = validate_predictions(df_out, expected_count=len(loader.requests))
    if errors:
        print("Validation errors encountered:")
        for err in errors:
            print(f"  ERROR: {err}")
        sys.exit(1)
    else:
        print("Validation PASSED! All schema, enum, and bound constraints verified.")

    # Write output.csv to repository root
    df_out.to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"\nPredictions written successfully to: {OUTPUT_CSV_PATH}")
    print(f"Total elapsed time: {time.time() - start_time:.2f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    run()
