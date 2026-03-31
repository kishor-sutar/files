# 💳 Payments Reconciliation Engine
### Onelab — AI Fitness Assessment Submission

> A payments platform records transactions instantly. The bank settles funds T+1 or T+2 days later.  
> At month-end, both ledgers should balance — **they don't. This engine finds out why.**

---

## 📁 Project Structure

```
files/
│
├── onelab_reconciliation.py        # Main reconciliation script (14 cells)
├── exception_report_march2026.csv  # Output: all flagged exceptions
├── platform_transactions.csv       # Output: synthetic platform ledger
├── bank_settlements.csv            # Output: synthetic bank settlements
└── README.md                       # This file
```

---

## 🧩 The Problem

A payments company's books don't balance at month-end.

| System | What it records |
|--------|----------------|
| **Platform** | Every transaction, instantly when the customer pays |
| **Bank** | Batched settlements, arriving T+1 or T+2 days later |

At month-end, every platform transaction should have a matching bank settlement. **They don't match. This tool finds every gap.**

---

## 🔍 Gap Types Detected

| # | Gap Type | Description |
|---|----------|-------------|
| 1 | `LATE_SETTLEMENT_NEXT_MONTH` | Transaction in March, bank settled in April |
| 2 | `ROUNDING_DIFFERENCE` | Platform vs bank amount differs by ≤ $0.05 (float/FX artefact) |
| 3 | `DUPLICATE_BANK_ENTRY` | Same `txn_id` + amount + date appears more than once in bank data |
| 4 | `UNEXPECTED_BANK_ENTRY` | Bank has a settlement with no matching platform transaction |
| 4b | `ORPHAN_REFUND_NO_ORIGINAL` | A refund exists on the platform with no original positive transaction |

---

## ⚙️ How It Works

```
Platform Transactions (85 rows)
        +
Bank Settlements (86 rows)
        │
        ▼
┌─────────────────────────┐
│   Scope to March 2026   │
└────────────┬────────────┘
             │
    ┌────────┴─────────┐
    ▼                  ▼
Deduplicate         Find matches
bank data           by txn_id
    │                  │
    ▼                  ▼
Flag duplicates    Compare amounts
Flag ghost         Flag rounding diffs
entries            Flag late settlements
                   Flag orphan refunds
             │
             ▼
   Exception Report CSV
   Summary by Issue Type
   Net Balance Difference
```

---

## 🚀 Quick Start

### Prerequisites

```bash
pip install pandas numpy
```

### Run

```bash
python onelab_reconciliation.py
```

### Output

```
Files written to: <your script directory>
  exception_report_march2026.csv
  platform_transactions.csv
  bank_settlements.csv
```

---

## 📊 Sample Results (March 2026)

```
Total platform captured : $81,342.58
Total bank settled      : $79,960.04
Net difference          : $1,382.54
```

| Issue Type | Count |
|------------|-------|
| LATE_SETTLEMENT_NEXT_MONTH | 4 |
| ROUNDING_DIFFERENCE | 3 |
| DUPLICATE_BANK_ENTRY | 2 |
| ORPHAN_REFUND_NO_ORIGINAL | 1 |
| UNEXPECTED_BANK_ENTRY | 1 |
| **Total exceptions** | **11** |

---

## 🧪 Test Cases

8 assertions run automatically at the end of the script:

```
[PASS ✓]  Late settlements detected
[PASS ✓]  Duplicate bank entries detected
[PASS ✓]  Unexpected bank entry (ghost) detected
[PASS ✓]  Orphan refund detected
[PASS ✓]  Rounding differences detected (3 rows expected)
[PASS ✓]  Duplicate bank entries appear exactly twice in report
[PASS ✓]  Clean matched transactions not flagged as missing/unexpected
[PASS ✓]  Net platform vs bank difference is non-zero
```

---

## 📋 Assumptions

1. Every platform transaction has a unique `txn_id`.
2. Normal bank settlement delay is **T+1 or T+2** calendar days.
3. A March transaction whose bank settlement falls in April is a **late settlement**.
4. Rounding differences **≤ $0.05 USD** are treated as float/FX artefacts; anything larger is a true mismatch.
5. A bank row with no matching platform `txn_id` is an **unexpected entry**.
6. Refunds are negative-amount rows; a refund with no positive original in the same month window is an **orphan**.
7. Duplicates are identified by the `(txn_id, amount, settlement_date)` triple appearing more than once in bank data.

---

## ⚠️ Known Limitations (What Would Go Wrong in Production)

1. **Hardcoded rounding threshold** — `$0.05 USD` is fixed. In multi-currency environments with live FX rates, this must be computed dynamically per currency pair.

2. **Duplicate detection is date-sensitive** — a re-batched settlement with the same `txn_id` but a shifted date bypasses the duplicate check silently.

3. **Orphan refund window is month-scoped** — a March refund against a February original transaction is incorrectly flagged as an orphan. Cross-month lookback is needed in production.

---

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.10+ | Core language |
| pandas | Data manipulation & reconciliation logic |
| numpy | Random data generation & numeric ops |
| uuid | Synthetic transaction ID generation |
| CSV | Output format for exception reports |

---

## 📝 Script Structure (Cell-by-Cell)

| Cell | Description |
|------|-------------|
| 1 | Helper utilities & constants |
| 2 | Generate platform transactions (with gaps planted) |
| 3 | Generate bank settlement data |
| 4 | Scope datasets to March 2026 |
| 5 | Detect duplicate bank entries |
| 6 | Detect unexpected bank entries |
| 7 | Detect orphan refunds |
| 8–9 | Detect missing & late settlements |
| 10 | Detect rounding & amount mismatches |
| 11–12 | Consolidate exception report + summary |
| 13 | Export CSVs |
| 14 | Run test cases |

---

## 👤 Author

Submitted as part of the **Onelab AI Fitness Assessment**  
Time limit: 2 hours | Tools: Any AI | Right answer: There isn't one