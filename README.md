# DataRecon — Retail Sales Reconciliation Tool

## Overview

DataRecon is a Python-based data reconciliation tool that validates retail sales data by comparing source and target datasets. It identifies missing records, extra records, field-level mismatches, duplicate order IDs, and missing values.

The project demonstrates how data engineers can validate data quality and detect discrepancies that may go unnoticed when an ETL pipeline completes successfully.

**Dataset note:** The Snitch-themed clothing sales dataset used in this project is simulated and uncleaned. It is not verified internal company data.

## Problem Statement

Data pipelines can complete successfully while still producing incorrect or incomplete data. Comparing only source and target row counts may not reveal missing records, extra records, or incorrect sales amounts.

DataRecon addresses this problem by implementing record-level and aggregate-level reconciliation checks.

## Tech Stack

- Python
- Pandas
- SQLite
- SQL
- Pytest

## Key Features

- Loads retail sales data from CSV files.
- Stores source and target datasets in SQLite tables.
- Compares source and target record counts.
- Identifies source-only and target-only records.
- Detects field-level mismatches, including sales amount differences.
- Reports duplicate order IDs without automatically deleting them.
- Generates missing-value quality reports.
- Exports reconciliation results as CSV and JSON reports.
- Includes controlled test discrepancies to verify the reconciliation logic.

## Architecture

CSV Source Data → Python and Pandas → SQLite Source/Target Tables → Reconciliation Checks → CSV and JSON Reports

## Validation Results

The initial test run used 2,500 source rows and a target dataset with controlled discrepancies.

| Validation | Result |
|---|---:|
| Source rows | 2,500 |
| Target rows | 2,500 |
| Source-only records | 1 |
| Target-only records | 1 |
| Field mismatches | 1 |
| Source sales total | 316,890.63 |
| Target sales total | 316,915.63 |
| Sales total difference | 25.00 |
| Duplicate Order ID groups | 44 |
| Rows with missing values | 2,387 |

These are results from the controlled test run, not a claim that the source data is production-clean.

## Generated Reports

- `summary.json` — reconciliation summary and aggregate comparisons.
- `source_only_records.csv` — records missing from the target.
- `target_only_records.csv` — records present only in the target.
- `field_mismatches.csv` — field-level discrepancies.
- `duplicate_order_ids.csv` — repeated order ID groups.
- `missing_values_report.csv` — missing-value counts and percentages.

## Run Locally

Install the dependencies:

```bash
py -m pip install -r requirements.txt
```

Run the reconciliation script:

```bash
py reconcile_snitch.py
```

Run automated tests, if Pytest is installed:

```bash
py -m pytest -q
```

## Important Design Decisions

- `Recon_Row_ID` is used to track individual rows because `Order_ID` is not unique in the dataset.
- The original CSV is kept unchanged.
