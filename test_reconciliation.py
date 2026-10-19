
import pandas as pd

from reconcile_snitch import create_test_target, reconcile


def test_missing_and_extra_records_are_detected():
    source = pd.DataFrame({
        "Recon_Row_ID": [1, 2, 3],
        "Order_ID": ["A", "B", "C"],
        "Sales_Amount": [100, 200, 300],
    })

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


def test_sales_amount_mismatch_is_detected():
    source = pd.DataFrame({
        "Recon_Row_ID": [1, 2],
        "Order_ID": ["A", "B"],
        "Sales_Amount": [100, 200],
    })

    target = source.copy()
    target.loc[target["Recon_Row_ID"] == 2, "Sales_Amount"] = 225

    source_only, target_only, mismatches = reconcile(
        source, target
    )

    assert source_only.empty
    assert target_only.empty
    assert (
        (mismatches["Recon_Row_ID"] == 2)
        & (mismatches["column_name"] == "Sales_Amount")
    ).any()
