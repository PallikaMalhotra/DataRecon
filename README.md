
# DataRecon Snitch

A Python-based data reconciliation tool that compares source and target sales datasets to identify missing records, extra records, field-level mismatches, and aggregate sales discrepancies.

## Problem Statement

ETL pipelines can complete successfully while still producing incorrect or incomplete target data. DataRecon Snitch helps identify these discrepancies by comparing source and target datasets at record and aggregate levels.

## Features

- Source-to-target row count validation
- Record-level comparison and mismatch reporting
- Detection of source-only and target-only records
- Total sales reconciliation
- Daily and product-category sales comparisons
- Missing-value and duplicate Order ID reports
- SQLite storage for source and target datasets
- Automated tests using pytest

## Tech Stack

- Python
- Pandas
- SQLite
- Pytest
- CSV

## Project Structure

```text
DataRecon_Snitch/
├── data/
│   ├── Snitch_Fashion_Sales_Uncleaned.csv
│   └── target_sales.csv
├── reports/
├── tests/
│   └── test_reconciliation.py
├── reconcile_snitch.py
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

Create and activate a virtual environment:

```bash
py -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
py -m pip install pandas pytest
```

## Run the Reconciliation

```bash
py reconcile_snitch.py
```

The script generates a SQLite database and reports under the `reports/` directory.

## Run Automated Tests

```bash
py -m pytest -q
```

## Reports Generated

- `summary.json`
- `source_only_records.csv`
- `target_only_records.csv`
- `field_mismatches.csv`
- `missing_values_report.csv`
- `duplicate_order_ids.csv`
- `daily_sales_reconciliation.csv`
- `category_sales_reconciliation.csv`

## Limitations

- Repeated Order IDs are matched using occurrence order. This assumes repeated IDs appear in the same order in source and target.
- Missing values in the source are reported, not automatically imputed.
- The current implementation is a local reconciliation tool; cloud orchestration is outside its scope.

## Future Improvements

- Use a stable transaction-line identifier for reliable record matching.
- Add configurable reconciliation rules and tolerances.
- Add tests for duplicate IDs and missing values.
- Integrate cloud storage and scheduled pipeline execution.
