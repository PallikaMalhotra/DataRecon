
import sqlite3
import json
from pathlib import Path

import pandas as pd


# -----------------------------
# 1. Project configuration
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "Snitch_Fashion_Sales_Uncleaned.csv"
)

DB_FILE = BASE_DIR / "datarecon_snitch.db"
REPORTS_DIR = BASE_DIR / "reports"

ROW_KEY = "Recon_Row_ID"


# -----------------------------
# 2. Load source dataset
# -----------------------------
def load_source():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}\n"
            "Check that the CSV is inside the data folder."
        )

    df = pd.read_csv(DATA_FILE)

    if df.empty:
        raise ValueError("The source dataset is empty.")

    # Stable row ID: Order_ID can repeat in this dataset.
    if ROW_KEY in df.columns:
        df = df.drop(columns=[ROW_KEY])

    df.insert(0, ROW_KEY, range(1, len(df) + 1))

    return df


# -----------------------------
# 3. Create target test data
# -----------------------------
def create_test_target(source):
    target = source.copy()

    # TEST 1: Remove one record from target.
    target = target[target[ROW_KEY] != 10].copy()

    # TEST 2: Change Sales_Amount for another record.
    mask = target[ROW_KEY] == 20

    if mask.any() and "Sales_Amount" in target.columns:
        old_value = pd.to_numeric(
            target.loc[mask, "Sales_Amount"],
            errors="coerce"
        ).fillna(0)

        target.loc[mask, "Sales_Amount"] = old_value + 25

    # TEST 3: Add an extra record to target.
    extra = source.iloc[[0]].copy()
    extra[ROW_KEY] = int(source[ROW_KEY].max()) + 1

    target = pd.concat(
        [target, extra],
        ignore_index=True
    )

    return target


# -----------------------------
# 4. Reconciliation checks
# -----------------------------
def reconcile(source, target):
    source_ids = set(source[ROW_KEY])
    target_ids = set(target[ROW_KEY])

    # Records present only in source or only in target.
    source_only_ids = sorted(source_ids - target_ids)
    target_only_ids = sorted(target_ids - source_ids)

    source_only = source[
        source[ROW_KEY].isin(source_only_ids)
    ].copy()

    target_only = target[
        target[ROW_KEY].isin(target_only_ids)
    ].copy()

    # Compare field values for records present in both tables.
    common_ids = sorted(source_ids & target_ids)

    source_common = source.set_index(ROW_KEY)
    target_common = target.set_index(ROW_KEY)

    mismatch_records = []

    compare_columns = [
        col for col in source.columns
        if col != ROW_KEY
    ]

    for row_id in common_ids:
        for col in compare_columns:
            source_value = source_common.at[row_id, col]
            target_value = target_common.at[row_id, col]

            # Two missing values are considered equal.
            if pd.isna(source_value) and pd.isna(target_value):
                continue

            # Numeric values should be compared numerically.
            source_num = pd.to_numeric(
                pd.Series([source_value]), errors="coerce"
            ).iloc[0]

            target_num = pd.to_numeric(
                pd.Series([target_value]), errors="coerce"
            ).iloc[0]

            if (
                pd.notna(source_num)
                and pd.notna(target_num)
            ):
                equal = source_num == target_num
            else:
                equal = str(source_value) == str(target_value)

            if not equal:
                mismatch_records.append({
                    ROW_KEY: row_id,
                    "column_name": col,
                    "source_value": (
                        None if pd.isna(source_value)
                        else str(source_value)
                    ),
                    "target_value": (
                        None if pd.isna(target_value)
                        else str(target_value)
                    )
                })

    mismatches = pd.DataFrame(
        mismatch_records,
        columns=[
            ROW_KEY,
            "column_name",
            "source_value",
            "target_value"
        ]
    )

    return source_only, target_only, mismatches


# -----------------------------
# 5. Data quality reports
# -----------------------------
def create_quality_reports(source):
    # Report missing values in each column.
    missing_records = []

    for col in source.columns:
        if col == ROW_KEY:
            continue

        missing_count = int(source[col].isna().sum())

        missing_records.append({
            "column_name": col,
            "missing_count": missing_count,
            "missing_percentage": round(
                source[col].isna().mean() * 100, 2
            )
        })

    missing_report = pd.DataFrame(missing_records)

    missing_report = missing_report.sort_values(
        "missing_count",
        ascending=False
    )

    # Repeated Order_ID groups are reported, not automatically deleted.
    if "Order_ID" in source.columns:
        order_ids = source["Order_ID"].astype("string").str.strip()

        valid_ids = source[
            order_ids.notna() & order_ids.ne("")
        ].copy()

        duplicate_report = (
            valid_ids.groupby("Order_ID", dropna=False)
            .size()
            .reset_index(name="row_count")
        )

        duplicate_report = duplicate_report[
            duplicate_report["row_count"] > 1
        ].sort_values(
            "row_count",
            ascending=False
        )
    else:
        duplicate_report = pd.DataFrame(
            columns=["Order_ID", "row_count"]
        )

    return missing_report, duplicate_report


# -----------------------------
# 6. Main pipeline
# -----------------------------
def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading source dataset...")

    source = load_source()

    print(f"Source rows loaded: {len(source)}")

    print("Creating target test data...")

    target = create_test_target(source)

    print("Running reconciliation checks...")

    source_only, target_only, mismatches = reconcile(
        source, target
    )

    missing_report, duplicate_report = (
        create_quality_reports(source)
    )

    # Calculate sales totals without treating missing values as zero
    # when the entire column is missing.
    source_sales = pd.to_numeric(
        source["Sales_Amount"], errors="coerce"
    ).sum(min_count=1) if "Sales_Amount" in source.columns else None

    target_sales = pd.to_numeric(
        target["Sales_Amount"], errors="coerce"
    ).sum(min_count=1) if "Sales_Amount" in target.columns else None

    sales_match = (
        source_sales == target_sales
        if source_sales is not None and target_sales is not None
        else False
    )

    # Store source and target in SQLite.
    with sqlite3.connect(DB_FILE) as conn:
        source.to_sql(
            "source_sales",
            conn,
            if_exists="replace",
            index=False
        )

        target.to_sql(
            "target_sales",
            conn,
            if_exists="replace",
            index=False
        )

    # Save reports.
    source_only.to_csv(
        REPORTS_DIR / "source_only_records.csv",
        index=False
    )

    target_only.to_csv(
        REPORTS_DIR / "target_only_records.csv",
        index=False
    )

    mismatches.to_csv(
        REPORTS_DIR / "field_mismatches.csv",
        index=False
    )

    missing_report.to_csv(
        REPORTS_DIR / "missing_values_report.csv",
        index=False
    )

    duplicate_report.to_csv(
        REPORTS_DIR / "duplicate_order_ids.csv",
        index=False
    )

    summary = {
        "source_rows": int(len(source)),
        "target_rows": int(len(target)),
        "row_count_match": bool(len(source) == len(target)),
        "source_only_records": int(len(source_only)),
        "target_only_records": int(len(target_only)),
        "field_mismatch_count": int(len(mismatches)),
        "source_sales_amount_total": (
            round(float(source_sales), 2)
            if source_sales is not None
            and pd.notna(source_sales)
            else None
        ),
        "target_sales_amount_total": (
            round(float(target_sales), 2)
            if target_sales is not None
            and pd.notna(target_sales)
            else None
        ),
        "sales_total_match": bool(sales_match),
        "duplicate_order_id_groups": int(
            len(duplicate_report)
        ),
        "rows_with_missing_values": int(
            source.drop(columns=[ROW_KEY])
            .isna()
            .any(axis=1)
            .sum()
        ),
        "test_mode": True
    }

    with open(
        REPORTS_DIR / "summary.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=4)

    # Print final results.
    print("\n========== RECONCILIATION SUMMARY ==========")
    print(json.dumps(summary, indent=4))

    print("\n========== GENERATED FILES ==========")
    print(f"SQLite database: {DB_FILE}")
    print(f"Reports folder: {REPORTS_DIR}")

    print("\nReconciliation testing completed.")


if __name__ == "__main__":
    main()
