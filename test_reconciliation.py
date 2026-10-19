
import pandas as pd

from reconcile_snitch import (
    create_test_target,
    reconcile,
    reconcile_daily_sales,
    reconcile_category_sales,
)


def sample_data():
    return pd.DataFrame({
        "Recon_Row_ID": [1, 2, 3],
        "Order_ID": ["A", "B", "C"],
        "Order_Date": [
            "2026-01-01",
            "2026-01-01",
            "2026-01-02",
        ],
        "Product_Category": [
            "Shirts",
            "Jeans",
            "Shirts",
        ],
        "Sales_Amount": [100.0, 200.0, 300.0],
    })


def test_missing_and_extra_records():
    source = sample_data()
    target = source.copy()

    target = target[target["Recon_Row_ID"] != 2].copy()

    extra = source.iloc[[0]].copy()
    extra["Recon_Row_ID"] = 4
    target = pd.concat([target, extra], ignore_index=True)

    source_only, target_only, mismatches = reconcile(
        source, target
    )

    assert source_only["Recon_Row_ID"].tolist() == [2]
    assert target_only["Recon_Row_ID"].tolist() == [4]


def test_sales_amount_mismatch():
    source = sample_data()
    target = source.copy()

    target.loc[
        target["Recon_Row_ID"] == 2,
        "Sales_Amount"
    ] = 225.0

    _, _, mismatches = reconcile(source, target)

    assert (
        (mismatches["Recon_Row_ID"] == 2)
        & (mismatches["column_name"] == "Sales_Amount")
    ).any()


def test_daily_sales_reconciliation():
    source = sample_data()
    target = source.copy()

    target.loc[
        target["Recon_Row_ID"] == 1,
        "Sales_Amount"
    ] = 125.0

    report = reconcile_daily_sales(source, target)

    jan1 = report[
        report["Order_Date"] == "2026-01-01"
    ]

    assert jan1.iloc[0]["status"] == "MISMATCH"


def test_category_sales_reconciliation():
    source = sample_data()
    target = source.copy()

    target.loc[
        target["Recon_Row_ID"] == 1,
        "Sales_Amount"
    ] = 125.0

    report = reconcile_category_sales(source, target)

    shirts = report[
        report["Product_Category"] == "Shirts"
    ]

    assert shirts.iloc[0]["status"] == "MISMATCH"
