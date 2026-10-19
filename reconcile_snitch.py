
import json
import sqlite3
from pathlib import Path

import pandas as pd


# ==================================================
# 1. CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "Snitch_Fashion_Sales_Uncleaned.csv"
)

DB_FILE = BASE_DIR / "datarecon_snitch.db"
REPORTS_DIR = BASE_DIR / "reports"

ROW_KEY = "Recon_Row_ID"

SALES_COLUMN = "Sales_Amount"
DATE_COLUMN = "Order_Date"
CATEGORY_COLUMN = "Product_Category"
ORDER_COLUMN = "Order_ID"


# ==================================================
# 2. LOAD SOURCE DATA
# ==================================================

def load_source():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}"
        )

    df = pd.read_csv(DATA_FILE)

    if df.empty:
        raise ValueError("Source dataset is empty.")

    required_columns = [
        ORDER_COLUMN,
        DATE_COLUMN,
        CATEGORY_COLUMN,
        SALES_COLUMN,
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Required columns missing: {missing_columns}"
        )

    # Create a stable key because Order_ID can repeat.
    if ROW_KEY in df.columns:
        df = df.drop(columns=[ROW_KEY])

    df.insert(0, ROW_KEY, range(1, len(df) + 1))

    return df


# ==================================================
# 3. CREATE TARGET TEST DATA
# ==================================================

def create_test_target(source):
    """
    Create a target copy with controlled discrepancies.
    The original CSV is never modified.
    """

    target = source.copy()

    # Test 1: Remove one record from target.
    target = target[
        target[ROW_KEY] != 10
    ].copy()

    # Test 2: Change sales amount for another record.
    mask = target[ROW_KEY] == 20

    if mask.any():
        old_value = pd.to_numeric(
            target.loc[mask, SALES_COLUMN],
            errors="coerce",
        ).fillna(0)

        target.loc[mask, SALES_COLUMN] = old_value + 25

    # Test 3: Add one extra target record.
    extra = source.iloc[[0]].copy()

    extra[ROW_KEY] = int(
        source[ROW_KEY].max()
    ) + 1

    target = pd.concat(
        [target, extra],
        ignore_index=True,
    )

    return target


# ==================================================
# 4. RECORD-LEVEL RECONCILIATION
# ==================================================

def reconcile(source, target):
    source_ids = set(source[ROW_KEY])
    target_ids = set(target[ROW_KEY])

    # Records that exist only in source.
    source_only_ids = sorted(
        source_ids - target_ids
    )

    # Records that exist only in target.
    target_only_ids = sorted(
        target_ids - source_ids
    )

    source_only = source[
        source[ROW_KEY].isin(source_only_ids)
    ].copy()

    target_only = target[
        target[ROW_KEY].isin(target_only_ids)
    ].copy()

    common_ids = sorted(
        source_ids & target_ids
    )

    source_indexed = source.set_index(ROW_KEY)
    target_indexed = target.set_index(ROW_KEY)

    mismatch_records = []

    compare_columns = [
        col for col in source.columns
        if col != ROW_KEY
    ]

    for row_id in common_ids:
        for col in compare_columns:

            source_value = source_indexed.at[
                row_id, col
            ]

            target_value = target_indexed.at[
                row_id, col
            ]

            # Both values missing means no mismatch.
            if (
                pd.isna(source_value)
                and pd.isna(target_value)
            ):
                continue

            # Compare numeric values numerically.
            source_num = pd.to_numeric(
                pd.Series([source_value]),
                errors="coerce",
            ).iloc[0]

            target_num = pd.to_numeric(
                pd.Series([target_value]),
                errors="coerce",
            ).iloc[0]

            if (
                pd.notna(source_num)
                and pd.notna(target_num)
            ):
                equal = source_num == target_num
            else:
                equal = (
                    str(source_value)
                    == str(target_value)
                )

            if not equal:
                mismatch_records.append({
                    ROW_KEY: row_id,
                    "column_name": col,
                    "source_value": (
                        None
                        if pd.isna(source_value)
                        else str(source_value)
                    ),
                    "target_value": (
                        None
                        if pd.isna(target_value)
                        else str(target_value)
                    ),
                })

    mismatches = pd.DataFrame(
        mismatch_records,
        columns=[
            ROW_KEY,
            "column_name",
            "source_value",
            "target_value",
        ],
    )

    return source_only, target_only, mismatches


# ==================================================
# 5. DATA QUALITY REPORTS
# ==================================================

def create_quality_reports(source):

    # Missing values by column.
    missing_records = []

    for col in source.columns:
        if col == ROW_KEY:
            continue

        missing_count = int(
            source[col].isna().sum()
        )

        missing_records.append({
            "column_name": col,
            "missing_count": missing_count,
            "missing_percentage": round(
                source[col].isna().mean() * 100,
                2,
            ),
        })

    missing_report = pd.DataFrame(
        missing_records
    ).sort_values(
        "missing_count",
        ascending=False,
    )

    # Repeated order IDs. Do not assume they are invalid.
    order_ids = (
        source[ORDER_COLUMN]
        .astype("string")
        .str.strip()
    )

    valid_order_mask = (
        order_ids.notna()
        & order_ids.ne("")
    )

    valid_orders = source[
        valid_order_mask
    ].copy()

    duplicate_report = (
        valid_orders.groupby(ORDER_COLUMN)
        .size()
        .reset_index(name="row_count")
    )

    duplicate_report = duplicate_report[
        duplicate_report["row_count"] > 1
    ].sort_values(
        "row_count",
        ascending=False,
    )

    return missing_report, duplicate_report


# ==================================================
# 6. PREPARE ANALYTICAL COLUMNS
# ==================================================

def prepare_analytics(df):
    result = df.copy()

    result[SALES_COLUMN] = pd.to_numeric(
        result[SALES_COLUMN],
        errors="coerce",
    )

    result[DATE_COLUMN] = pd.to_datetime(
        result[DATE_COLUMN],
        errors="coerce",
        dayfirst=True,
    ).dt.strftime("%Y-%m-%d")

    return result


# ==================================================
# 7. DAILY SALES RECONCILIATION
# ==================================================

def reconcile_daily_sales(source, target):
    source = prepare_analytics(source)
    target = prepare_analytics(target)

    source_daily = (
        source.groupby(
            DATE_COLUMN,
            dropna=False,
        )[SALES_COLUMN]
        .sum(min_count=1)
        .rename("source_sales")
    )

    target_daily = (
        target.groupby(
            DATE_COLUMN,
            dropna=False,
        )[SALES_COLUMN]
        .sum(min_count=1)
        .rename("target_sales")
    )

    report = pd.concat(
        [source_daily, target_daily],
        axis=1,
    )

    report["difference"] = (
        report["target_sales"]
        - report["source_sales"]
    )

    report["status"] = report["difference"].apply(
        lambda value: (
            "MATCH"
            if pd.notna(value)
            and abs(value) < 0.01
            else "MISMATCH"
        )
    )

    return report.reset_index()


# ==================================================
# 8. CATEGORY-WISE SALES RECONCILIATION
# ==================================================

def reconcile_category_sales(source, target):
    source = prepare_analytics(source)
    target = prepare_analytics(target)

    source_category = (
        source.groupby(
            CATEGORY_COLUMN,
            dropna=False,
        )[SALES_COLUMN]
        .sum(min_count=1)
        .rename("source_sales")
    )

    target_category = (
        target.groupby(
            CATEGORY_COLUMN,
            dropna=False,
        )[SALES_COLUMN]
        .sum(min_count=1)
        .rename("target_sales")
    )

    report = pd.concat(
        [source_category, target_category],
        axis=1,
    )

    report["difference"] = (
        report["target_sales"]
        - report["source_sales"]
    )

    report["status"] = report["difference"].apply(
        lambda value: (
            "MATCH"
            if pd.notna(value)
            and abs(value) < 0.01
            else "MISMATCH"
        )
    )

    return report.reset_index()


# ==================================================
# 9. MAIN PIPELINE
# ==================================================

def main():
    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading source dataset...")

    source = load_source()

    print(f"Source rows: {len(source)}")

    print("Creating controlled target test data...")

    target = create_test_target(source)

    print("Running record-level reconciliation...")

    source_only, target_only, mismatches = (
        reconcile(source, target)
    )

    print("Running data quality checks...")

    missing_report, duplicate_report = (
        create_quality_reports(source)
    )

    print("Running daily sales reconciliation...")

    daily_report = reconcile_daily_sales(
        source,
        target,
    )

    print("Running category sales reconciliation...")

    category_report = reconcile_category_sales(
        source,
        target,
    )

    # Calculate overall sales totals.
    source_sales = pd.to_numeric(
        source[SALES_COLUMN],
        errors="coerce",
    ).sum(min_count=1)

    target_sales = pd.to_numeric(
        target[SALES_COLUMN],
        errors="coerce",
    ).sum(min_count=1)

    sales_match = (
        pd.notna(source_sales)
        and pd.notna(target_sales)
        and abs(source_sales - target_sales) < 0.01
    )

    # Store source and target in SQLite.
    with sqlite3.connect(DB_FILE) as conn:
        source.to_sql(
            "source_sales",
            conn,
            if_exists="replace",
            index=False,
        )

        target.to_sql(
            "target_sales",
            conn,
            if_exists="replace",
            index=False,
        )

    # Export reconciliation reports.
    source_only.to_csv(
        REPORTS_DIR / "source_only_records.csv",
        index=False,
    )

    target_only.to_csv(
        REPORTS_DIR / "target_only_records.csv",
        index=False,
    )

    mismatches.to_csv(
        REPORTS_DIR / "field_mismatches.csv",
        index=False,
    )

    missing_report.to_csv(
        REPORTS_DIR / "missing_values_report.csv",
        index=False,
    )

    duplicate_report.to_csv(
        REPORTS_DIR / "duplicate_order_ids.csv",
        index=False,
    )

    daily_report.to_csv(
        REPORTS_DIR / "daily_sales_reconciliation.csv",
        index=False,
    )

    category_report.to_csv(
        REPORTS_DIR / "category_sales_reconciliation.csv",
        index=False,
    )

    # Build summary.
    summary = {
        "source_rows": int(len(source)),
        "target_rows": int(len(target)),
        "row_count_match": bool(
            len(source) == len(target)
        ),
        "source_only_records": int(
            len(source_only)
        ),
        "target_only_records": int(
            len(target_only)
        ),
        "field_mismatch_count": int(
            len(mismatches)
        ),
        "source_sales_amount_total": (
            round(float(source_sales), 2)
            if pd.notna(source_sales)
            else None
        ),
        "target_sales_amount_total": (
            round(float(target_sales), 2)
            if pd.notna(target_sales)
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
        "daily_groups_with_mismatch": int(
            (daily_report["status"] == "MISMATCH").sum()
        ),
        "category_groups_with_mismatch": int(
            (category_report["status"] == "MISMATCH").sum()
        ),
        "test_mode": True,
    }

    with open(
        REPORTS_DIR / "summary.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=4,
        )

    print("\n========== RECONCILIATION SUMMARY ==========")
    print(json.dumps(summary, indent=4))

    print("\n========== GENERATED REPORTS ==========")

    for report_file in sorted(
        REPORTS_DIR.iterdir()
    ):
        if report_file.is_file():
            print(report_file.name)

    print(f"\nSQLite database: {DB_FILE}")
    print("Reconciliation completed successfully.")


if __name__ == "__main__":
    main()
