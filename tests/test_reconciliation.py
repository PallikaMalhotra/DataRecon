
import pandas as pd

from reconcile_snitch import reconcile, aggregate_reconciliation


def sample_data():
    source = pd.DataFrame({
        "Order_ID": ["101", "102", "103"],
        "Order_Date": ["2026-01-01", "2026-01-01", "2026-01-02"],
        "Product_Category": ["T-Shirt", "Jeans", "T-Shirt"],
        "Sales_Amount": [100.0, 200.0, 150.0],
    })
    return source, source.copy()


def test_identical_data_has_no_differences():
    source, target = sample_data()
    source_only, target_only, mismatches = reconcile(source, target)

    assert len(source_only) == 0
    assert len(target_only) == 0
    assert len(mismatches) == 0


def test_changed_sales_amount_is_detected():
    source, target = sample_data()
    target.loc[0, "Sales_Amount"] = 125.0

    source_only, target_only, mismatches = reconcile(source, target)

    assert len(source_only) == 0
    assert len(target_only) == 0
    assert "Sales_Amount" in mismatches["column_name"].tolist()


def test_extra_target_record_is_detected():
    source, target = sample_data()
    extra = pd.DataFrame([{
        "Order_ID": "104",
        "Order_Date": "2026-01-03",
        "Product_Category": "Jeans",
        "Sales_Amount": 300.0,
    }])
    target = pd.concat([target, extra], ignore_index=True)

    source_only, target_only, mismatches = reconcile(source, target)

    assert len(source_only) == 0
    assert len(target_only) == 1
    assert str(target_only.iloc[0]["Order_ID"]) == "104"


def test_daily_sales_mismatch_is_detected():
    source, target = sample_data()
    target.loc[0, "Sales_Amount"] = 125.0

    report = aggregate_reconciliation(source, target, "Order_Date")

    assert (report["status"] == "MISMATCH").sum() == 1
