
import json
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

SOURCE_FILE = DATA_DIR / "Snitch_Fashion_Sales_Uncleaned.csv"
TARGET_FILE = DATA_DIR / "target_sales.csv"
DB_FILE = BASE_DIR / "datarecon_snitch.db"

ORDER_COL = "Order_ID"
DATE_COL = "Order_Date"
CATEGORY_COL = "Product_Category"
SALES_COL = "Sales_Amount"


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path)
    df.columns = df.columns.astype(str).str.strip()

    if df.empty:
        raise ValueError(f"{path.name} contains no rows.")

    return df


def prepare_data(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    for col in [
        ORDER_COL, CATEGORY_COL, "Customer_Name",
        "Product_Name", "City", "Segment"
    ]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    df[SALES_COL] = pd.to_numeric(df[SALES_COL], errors="coerce")

    df[DATE_COL] = pd.to_datetime(
        df[DATE_COL],
        format="mixed",
        errors="coerce",
        dayfirst=True
    ).dt.strftime("%Y-%m-%d")

    return df


def validate_columns(df, filename):
    required = [ORDER_COL, DATE_COL, CATEGORY_COL, SALES_COL]
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"{filename} is missing {missing}. "
            f"Available columns: {df.columns.tolist()}"
        )



def reconcile(source, target):
    source = source.copy().reset_index(drop=True)
    target = target.copy().reset_index(drop=True)

    source.columns = source.columns.astype(str).str.strip()
    target.columns = target.columns.astype(str).str.strip()

    key_col = "Order_ID"

    if key_col not in source.columns or key_col not in target.columns:
        raise ValueError(
            f"Source columns: {source.columns.tolist()}\n"
            f"Target columns: {target.columns.tolist()}"
        )

    # Compare records by occurrence of Order_ID.
    source["_occurrence"] = source.groupby(
        key_col, dropna=False
    ).cumcount()
    target["_occurrence"] = target.groupby(
        key_col, dropna=False
    ).cumcount()

    key_columns = [key_col, "_occurrence"]

    # Reset the index after joining so Order_ID stays a normal column.
    source_indexed = source.set_index(key_columns, drop=False)
    target_indexed = target.set_index(key_columns, drop=False)

    source_keys = set(source_indexed.index)
    target_keys = set(target_indexed.index)

    source_only_keys = source_keys - target_keys
    target_only_keys = target_keys - source_keys
    common_keys = source_keys & target_keys

    source_only = (
        source_indexed.loc[list(source_only_keys)]
        .reset_index(drop=True)
        if source_only_keys else source.iloc[0:0].copy()
    )

    target_only = (
        target_indexed.loc[list(target_only_keys)]
        .reset_index(drop=True)
        if target_only_keys else target.iloc[0:0].copy()
    )

    source_only = source_only.drop(
        columns=["_occurrence"], errors="ignore"
    )
    target_only = target_only.drop(
        columns=["_occurrence"], errors="ignore"
    )

    compare_columns = [
        col for col in source.columns
        if col != "_occurrence" and col in target.columns
    ]

    mismatch_rows = []

    for key in sorted(common_keys, key=str):
        source_row = source_indexed.loc[key]
        target_row = target_indexed.loc[key]

        for col in compare_columns:
            a = source_row[col]
            b = target_row[col]

            if pd.isna(a) and pd.isna(b):
                continue

            if pd.isna(a) != pd.isna(b):
                equal = False
            else:
                equal = str(a).strip() == str(b).strip()

            if not equal:
                mismatch_rows.append({
                    "Order_ID": key[0],
                    "occurrence": key[1],
                    "column_name": col,
                    "source_value": None if pd.isna(a) else str(a),
                    "target_value": None if pd.isna(b) else str(b),
                })

    mismatches = pd.DataFrame(
        mismatch_rows,
        columns=[
            "Order_ID",
            "occurrence",
            "column_name",
            "source_value",
            "target_value",
        ],
    )

    return source_only, target_only, mismatches


def create_quality_reports(source):
    missing_report = pd.DataFrame([
        {
            "column_name": col,
            "missing_count": int(source[col].isna().sum()),
            "missing_percentage": round(
                source[col].isna().mean() * 100, 2
            )
        }
        for col in source.columns
    ]).sort_values("missing_count", ascending=False)

    ids = source[ORDER_COL].dropna()
    duplicates = (
        ids.value_counts()
        .loc[lambda x: x > 1]
        .rename_axis(ORDER_COL)
        .reset_index(name="row_count")
    )

    return missing_report, duplicates


def aggregate_reconciliation(source, target, group_column):
    source_totals = (
        source.groupby(group_column, dropna=False)[SALES_COL]
        .sum(min_count=1)
        .rename("source_sales")
    )
    target_totals = (
        target.groupby(group_column, dropna=False)[SALES_COL]
        .sum(min_count=1)
        .rename("target_sales")
    )

    report = pd.concat([source_totals, target_totals], axis=1)
    report["difference"] = (
        report["target_sales"] - report["source_sales"]
    )
    report["status"] = report["difference"].apply(
        lambda x: "MATCH"
        if pd.notna(x) and abs(x) < 0.01
        else "MISMATCH"
    )

    return report.reset_index()


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    source = prepare_data(load_csv(SOURCE_FILE))
    target = prepare_data(load_csv(TARGET_FILE))

    validate_columns(source, SOURCE_FILE.name)
    validate_columns(target, TARGET_FILE.name)

    if set(source.columns) != set(target.columns):
        raise ValueError(
            "Source and target columns differ.\n"
            f"Source-only: {sorted(set(source.columns)-set(target.columns))}\n"
            f"Target-only: {sorted(set(target.columns)-set(source.columns))}"
        )

    target = target[source.columns]

    source_only, target_only, mismatches = reconcile(source, target)
    missing, duplicates = create_quality_reports(source)

    daily = aggregate_reconciliation(source, target, DATE_COL)
    categories = aggregate_reconciliation(source, target, CATEGORY_COL)

    source_total = source[SALES_COL].sum(min_count=1)
    target_total = target[SALES_COL].sum(min_count=1)

    summary = {
        "source_rows": int(len(source)),
        "target_rows": int(len(target)),
        "row_count_match": bool(len(source) == len(target)),
        "source_only_records": int(len(source_only)),
        "target_only_records": int(len(target_only)),
        "field_mismatch_count": int(len(mismatches)),
        "source_sales_total": round(float(source_total), 2)
            if pd.notna(source_total) else None,
        "target_sales_total": round(float(target_total), 2)
            if pd.notna(target_total) else None,
        "sales_total_match": bool(
            pd.notna(source_total) and pd.notna(target_total)
            and abs(source_total - target_total) < 0.01
        ),
        "duplicate_order_id_groups": int(len(duplicates)),
        "rows_with_missing_values": int(source.isna().any(axis=1).sum()),
        "daily_groups_with_mismatch": int(
            (daily["status"] == "MISMATCH").sum()
        ),
        "category_groups_with_mismatch": int(
            (categories["status"] == "MISMATCH").sum()
        )
    }

    with sqlite3.connect(DB_FILE) as conn:
        source.to_sql("source_sales", conn, if_exists="replace", index=False)
        target.to_sql("target_sales", conn, if_exists="replace", index=False)

    reports = {
        "source_only_records.csv": source_only,
        "target_only_records.csv": target_only,
        "field_mismatches.csv": mismatches,
        "missing_values_report.csv": missing,
        "duplicate_order_ids.csv": duplicates,
        "daily_sales_reconciliation.csv": daily,
        "category_sales_reconciliation.csv": categories
    }

    for name, df in reports.items():
        df.to_csv(REPORTS_DIR / name, index=False)

    with open(REPORTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print(json.dumps(summary, indent=4))
    print(f"\nDatabase: {DB_FILE}")
    print(f"Reports: {REPORTS_DIR}")
    print("Reconciliation completed.")


if __name__ == "__main__":
    main()
