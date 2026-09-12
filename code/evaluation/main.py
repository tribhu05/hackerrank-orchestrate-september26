"""
Evaluation and verification script for Buy or Wait? challenge.
Audits output.csv for schema compliance, verifies safety invariants,
and evaluates performance against public benchmark samples.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.config import (
    OUTPUT_CSV_PATH,
    REQUESTS_CSV,
    SAMPLE_REQUESTS_CSV,
    ALLOWED_AFFORDABILITY_STATUS,
    ALLOWED_PAYMENT_METHODS,
)

def evaluate_output(output_csv_path=OUTPUT_CSV_PATH):
    print("=" * 60)
    print("HackerRank Orchestrate — Buy or Wait? Solution Evaluation")
    print("=" * 60)

    if not Path(output_csv_path).exists():
        print(f"ERROR: {output_csv_path} does not exist!")
        return False

    df_out = pd.read_csv(output_csv_path)
    df_reqs = pd.read_csv(REQUESTS_CSV) if REQUESTS_CSV.exists() else None

    # 1. Schema Audit
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

    print("\n[1/4] Auditing Output CSV Schema...")
    col_errors = []
    if list(df_out.columns) != required_cols:
        col_errors.append(f"Column order or names incorrect:\n  Got:      {list(df_out.columns)}\n  Expected: {required_cols}")
    else:
        print("  [OK] Column headers and exact order verified.")

    expected_len = len(df_reqs) if df_reqs is not None else 250
    if len(df_out) != expected_len:
        col_errors.append(f"Row count mismatch: got {len(df_out)}, expected {expected_len}")
    else:
        print(f"  [OK] Exact row count verified ({len(df_out)} rows).")

    if df_out["request_id"].duplicated().any():
        dups = df_out[df_out["request_id"].duplicated()]["request_id"].tolist()
        col_errors.append(f"Duplicate request IDs: {dups}")
    else:
        print("  [OK] No duplicate request IDs.")

    # 2. Value Constraints Audit
    print("\n[2/4] Auditing Value Constraints & Enums...")
    val_errors = []
    for idx, r in df_out.iterrows():
        rid = r["request_id"]
        status = r["affordability_status"]
        method = r["recommended_payment_method"]
        safe_amt = r["amount_safe_to_pay"]
        plan = str(r["payment_plan"]).strip()
        earliest_dt = str(r["earliest_date_for_full_payment"]).strip()

        if status not in ALLOWED_AFFORDABILITY_STATUS:
            val_errors.append(f"[{rid}] Invalid affordability_status: {status}")

        if method not in ALLOWED_PAYMENT_METHODS:
            val_errors.append(f"[{rid}] Invalid recommended_payment_method: {method}")

        if pd.isna(safe_amt) or safe_amt < 0:
            val_errors.append(f"[{rid}] Invalid amount_safe_to_pay: {safe_amt}")

        # Check requested_amount bounds if requests.csv is available
        if df_reqs is not None:
            req_match = df_reqs[df_reqs["request_id"] == rid]
            if not req_match.empty:
                req_amt = float(req_match.iloc[0]["requested_amount"])
                if safe_amt > req_amt + 1e-4:
                    val_errors.append(f"[{rid}] amount_safe_to_pay ({safe_amt}) > requested_amount ({req_amt})")

        if status == "affordable_now":
            if not earliest_dt or earliest_dt == "nan":
                val_errors.append(f"[{rid}] affordable_now must have earliest_date_for_full_payment set")

        if method == "not_recommended":
            if plan != "none":
                val_errors.append(f"[{rid}] not_recommended must have payment_plan = 'none'")

        if method in {"full_payment", "partial_payment", "installments", "wait"}:
            if plan == "none" or not plan:
                val_errors.append(f"[{rid}] {method} must have valid payment_plan, got '{plan}'")

    if not val_errors:
        print("  [OK] All enums, numeric bounds, and plan formats verified.")
    else:
        print(f"  [FAIL] Found {len(val_errors)} value constraint errors:")
        for err in val_errors[:10]:
            print(f"    - {err}")

    # 3. Distribution Summary
    print("\n[3/4] Prediction Distribution:")
    print("Affordability Status:")
    for k, v in df_out["affordability_status"].value_counts().items():
        print(f"  {k:25s}: {v:3d} ({v/len(df_out)*100:.1f}%)")

    print("\nRecommended Payment Method:")
    for k, v in df_out["recommended_payment_method"].value_counts().items():
        print(f"  {k:25s}: {v:3d} ({v/len(df_out)*100:.1f}%)")

    # 4. Benchmark against sample_requests.csv if available
    print("\n[4/4] Sample Benchmark Validation...")
    if SAMPLE_REQUESTS_CSV.exists():
        from code.data_loader import DataLoader
        from code.decision_engine import DecisionEngine

        loader = DataLoader()
        engine = DecisionEngine(loader)
        samples = loader.samples

        status_correct = 0
        method_correct = 0
        plan_correct = 0
        safe_mae = []

        for s in samples:
            pred = engine.evaluate_request(s)
            s_match = pred["affordability_status"] == s["affordability_status"]
            m_match = pred["recommended_payment_method"] == s["recommended_payment_method"]
            p_match = pred["payment_plan"] == s["payment_plan"]
            safe_diff = abs(pred["amount_safe_to_pay"] - s["amount_safe_to_pay"])

            if s_match:
                status_correct += 1
            if m_match:
                method_correct += 1
            if p_match:
                plan_correct += 1
            safe_mae.append(safe_diff)

        total_samples = len(samples)
        print(f"  Sample Benchmark Results ({total_samples} samples):")
        print(f"  - Affordability Status Accuracy : {status_correct}/{total_samples} ({status_correct/total_samples*100:.1f}%)")
        print(f"  - Payment Method Accuracy       : {method_correct}/{total_samples} ({method_correct/total_samples*100:.1f}%)")
        print(f"  - Payment Plan Exact Matches    : {plan_correct}/{total_samples} ({plan_correct/total_samples*100:.1f}%)")
        print(f"  - Amount Safe To Pay Mean Diff  : {np.mean(safe_mae):.2f}")

    all_errors = col_errors + val_errors
    if all_errors:
        print(f"\nEvaluation FAILED with {len(all_errors)} errors.")
        return False
    else:
        print("\nAll Evaluation Checks PASSED Successfully!")
        return True

if __name__ == "__main__":
    success = evaluate_output()
    sys.exit(0 if success else 1)
