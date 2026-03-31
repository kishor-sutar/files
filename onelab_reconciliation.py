# =============================================================================
# ONELAB — AI FITNESS ASSESSMENT
# Payments Reconciliation Engine
# Author: Submission-ready Python script (Jupyter Notebook style)
# =============================================================================

# %% [markdown]
# # Payments Reconciliation Engine
# **Problem:** A payments platform records transactions instantly; the bank settles
# funds T+1 or T+2 days later. At month-end, both ledgers should balance — they don't.
# **Goal:** Detect every class of mismatch and surface a clean exception report.

# %% [markdown]
# ## Assumptions
# 1. Every platform transaction has a unique `txn_id` (UUID-style string).
# 2. Normal bank settlement delay is 1–2 calendar days (`T+1` or `T+2`).
# 3. A transaction dated 30 or 31 March whose bank settlement falls in April is a
#    **late settlement** (crosses month boundary).
# 4. Rounding differences ≤ ±0.05 USD are float/FX artefacts; anything larger is an
#    amount mismatch.
# 5. A bank row with no matching `txn_id` in the platform is an **unexpected entry**
#    (could be manual adjustment, fraud, or a refund orphan).
# 6. Refunds are represented as negative-amount rows on the platform; a refund with no
#    original positive transaction is flagged as **orphan refund**.
# 7. Duplicates are identified by (`txn_id`, `amount`, `settlement_date`) triple
#    appearing more than once in the bank dataset.

# %%
import pandas as pd
import numpy as np
import uuid
import random
from datetime import date, timedelta
import warnings
warnings.filterwarnings("ignore")

random.seed(42)
np.random.seed(42)

# =============================================================================
# CELL 1 — Helper utilities
# =============================================================================

def random_txn_id():
    return "TXN-" + str(uuid.uuid4())[:8].upper()

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

MONTH_START = date(2026, 3, 1)
MONTH_END   = date(2026, 3, 31)
NEXT_MONTH  = date(2026, 4, 2)   # latest possible late-settlement date

# =============================================================================
# CELL 2 — Generate platform transactions
# =============================================================================

N_NORMAL = 80   # clean transactions that will settle on time

platform_rows = []
for _ in range(N_NORMAL):
    txn_id  = random_txn_id()
    txn_date = random_date(MONTH_START, date(2026, 3, 28))   # leave room for T+2
    amount   = round(random.uniform(10.00, 2000.00), 2)
    platform_rows.append({
        "txn_id"   : txn_id,
        "txn_date" : txn_date,
        "amount"   : amount,
        "currency" : "USD",
        "status"   : "CAPTURED",
    })

# --- GAP TYPE 1: Late settlements (transactions on 29–31 March settle in April) ---
LATE_IDS = []
for i in range(4):
    txn_id   = random_txn_id()
    txn_date = date(2026, 3, 29) + timedelta(days=i % 3)   # 29, 30, 31 Mar
    amount   = round(random.uniform(100.00, 800.00), 2)
    platform_rows.append({
        "txn_id"  : txn_id,
        "txn_date": txn_date,
        "amount"  : amount,
        "currency": "USD",
        "status"  : "CAPTURED",
    })
    LATE_IDS.append((txn_id, amount, txn_date))

# --- GAP TYPE 4: Refund with no original transaction ---
ORPHAN_REFUND_ID = random_txn_id()
platform_rows.append({
    "txn_id"  : ORPHAN_REFUND_ID,
    "txn_date": date(2026, 3, 15),
    "amount"  : -250.00,          # negative = refund
    "currency": "USD",
    "status"  : "REFUNDED",
})
# NOTE: we deliberately do NOT add a matching positive transaction for this refund

platform_df = pd.DataFrame(platform_rows)
platform_df["txn_date"] = pd.to_datetime(platform_df["txn_date"])

print(f"Platform transactions: {len(platform_df)} rows")
print(platform_df.head(5).to_string(index=False))

# =============================================================================
# CELL 3 — Generate bank settlement data
# =============================================================================

bank_rows = []

# Settle every NORMAL transaction within T+1 or T+2
for _, row in platform_df[platform_df["status"] == "CAPTURED"].iterrows():
    settle_date = row["txn_date"] + timedelta(days=random.choice([1, 2]))
    bank_rows.append({
        "txn_id"         : row["txn_id"],
        "settlement_date": settle_date,
        "settled_amount" : row["amount"],
    })

# --- GAP TYPE 1 fix: move late-settlement rows to April ---
for txn_id, amount, txn_date in LATE_IDS:
    # overwrite the T+1/T+2 row with an April date
    for r in bank_rows:
        if r["txn_id"] == txn_id:
            r["settlement_date"] = pd.Timestamp(date(2026, 4, 1))
            break

# --- GAP TYPE 2: Rounding difference on 3 rows ---
ROUNDING_IDS = random.sample(
    list(platform_df[platform_df["status"] == "CAPTURED"]["txn_id"]), 3
)
for r in bank_rows:
    if r["txn_id"] in ROUNDING_IDS:
        r["settled_amount"] = round(r["settled_amount"] + random.choice([-0.01, 0.01]), 2)

# --- GAP TYPE 3: Duplicate entry (same txn_id settled twice) ---
DUPE_TXN = random.choice(
    [r["txn_id"] for r in bank_rows
     if r["settlement_date"] <= pd.Timestamp(MONTH_END)]
)
original = next(r for r in bank_rows if r["txn_id"] == DUPE_TXN)
bank_rows.append({
    "txn_id"         : original["txn_id"],
    "settlement_date": original["settlement_date"],
    "settled_amount" : original["settled_amount"],
})

# --- GAP TYPE 4: Unexpected bank entry (no platform record) ---
GHOST_ID = random_txn_id()
bank_rows.append({
    "txn_id"         : GHOST_ID,
    "settlement_date": pd.Timestamp(date(2026, 3, 20)),
    "settled_amount" : 499.99,
})

bank_df = pd.DataFrame(bank_rows)
bank_df["settlement_date"] = pd.to_datetime(bank_df["settlement_date"])

print(f"\nBank settlement rows: {len(bank_df)} rows")
print(bank_df.head(5).to_string(index=False))

# =============================================================================
# CELL 4 — Scope: restrict reconciliation to March 2026
# =============================================================================

RECON_START = pd.Timestamp("2026-03-01")
RECON_END   = pd.Timestamp("2026-03-31")

platform_march = platform_df[
    (platform_df["txn_date"] >= RECON_START) &
    (platform_df["txn_date"] <= RECON_END)
].copy()

bank_march = bank_df[
    (bank_df["settlement_date"] >= RECON_START) &
    (bank_df["settlement_date"] <= RECON_END)
].copy()

print(f"Platform (March): {len(platform_march)} | Bank (March): {len(bank_march)}")

# =============================================================================
# CELL 5 — DETECT GAP TYPE 3: Duplicates in bank data
# =============================================================================

dupe_mask = bank_march.duplicated(
    subset=["txn_id", "settled_amount", "settlement_date"], keep=False
)
duplicates_df = bank_march[dupe_mask].copy()
duplicates_df["issue"] = "DUPLICATE_BANK_ENTRY"

print(f"\n[GAP 3] Duplicate bank entries: {len(duplicates_df)}")
print(duplicates_df.to_string(index=False))

# Drop duplicates from bank before further analysis (keep first occurrence)
bank_march_deduped = bank_march.drop_duplicates(
    subset=["txn_id", "settled_amount", "settlement_date"], keep="first"
)

# =============================================================================
# CELL 6 — DETECT GAP TYPE 4: Unexpected bank entries (no platform match)
# =============================================================================

platform_ids = set(platform_march["txn_id"])
bank_ids     = set(bank_march_deduped["txn_id"])

unexpected_ids = bank_ids - platform_ids
unexpected_df  = bank_march_deduped[
    bank_march_deduped["txn_id"].isin(unexpected_ids)
].copy()
unexpected_df["issue"] = "UNEXPECTED_BANK_ENTRY"

print(f"\n[GAP 4] Unexpected bank entries: {len(unexpected_df)}")
print(unexpected_df.to_string(index=False))

# =============================================================================
# CELL 7 — DETECT GAP TYPE 4b: Orphan refunds (negative amount, no original)
# =============================================================================

refunds = platform_march[platform_march["amount"] < 0].copy()
positive_ids = set(platform_march[platform_march["amount"] > 0]["txn_id"])

orphan_refunds = refunds[~refunds["txn_id"].isin(positive_ids)].copy()
# A refund references the *original* txn via txn_id in real systems; here we
# flag refund rows whose txn_id has no positive counterpart in the same period.
orphan_refunds["issue"] = "ORPHAN_REFUND_NO_ORIGINAL"

print(f"\n[GAP 4b] Orphan refunds: {len(orphan_refunds)}")
print(orphan_refunds.to_string(index=False))

# =============================================================================
# CELL 8 — DETECT GAP TYPE 1: Missing settlements (platform has it, bank doesn't)
# =============================================================================

settled_ids       = set(bank_march_deduped["txn_id"])
positive_platform = platform_march[platform_march["amount"] > 0]
missing_ids       = set(positive_platform["txn_id"]) - settled_ids - unexpected_ids

missing_df = positive_platform[
    positive_platform["txn_id"].isin(missing_ids)
].copy()
missing_df["issue"] = "MISSING_SETTLEMENT"

print(f"\n[GAP 1] Missing settlements in March bank data: {len(missing_df)}")
print(missing_df.to_string(index=False))

# =============================================================================
# CELL 9 — DETECT GAP TYPE 1b: Late settlements (settled in April)
# =============================================================================

bank_april = bank_df[
    (bank_df["settlement_date"] >= pd.Timestamp("2026-04-01")) &
    (bank_df["settlement_date"] <= pd.Timestamp("2026-04-07"))   # grace window
].copy()

late_ids = set(bank_april["txn_id"]) & set(missing_df["txn_id"])

late_df = missing_df[missing_df["txn_id"].isin(late_ids)].copy()
late_df["issue"] = "LATE_SETTLEMENT_NEXT_MONTH"
late_df = late_df.merge(
    bank_april[["txn_id", "settlement_date"]].rename(
        columns={"settlement_date": "actual_settlement_date"}),
    on="txn_id", how="left"
)

truly_missing_df = missing_df[~missing_df["txn_id"].isin(late_ids)].copy()

print(f"\n[GAP 1b] Late settlements (settled in April): {len(late_df)}")
print(late_df[["txn_id", "txn_date", "amount", "actual_settlement_date", "issue"]].to_string(index=False))

print(f"\n[GAP 1c] Truly missing (not even in April): {len(truly_missing_df)}")

# =============================================================================
# CELL 10 — DETECT GAP TYPE 2: Amount / rounding mismatches
# =============================================================================

matched_df = platform_march[platform_march["amount"] > 0].merge(
    bank_march_deduped[["txn_id", "settled_amount"]],
    on="txn_id", how="inner"
)

matched_df["delta"] = (matched_df["settled_amount"] - matched_df["amount"]).round(4)

ROUNDING_THRESHOLD = 0.05   # assumption

rounding_df = matched_df[
    (matched_df["delta"].abs() > 0) &
    (matched_df["delta"].abs() <= ROUNDING_THRESHOLD)
].copy()
rounding_df["issue"] = "ROUNDING_DIFFERENCE"

amount_mismatch_df = matched_df[
    matched_df["delta"].abs() > ROUNDING_THRESHOLD
].copy()
amount_mismatch_df["issue"] = "AMOUNT_MISMATCH"

print(f"\n[GAP 2a] Rounding differences (≤ $0.05): {len(rounding_df)}")
print(rounding_df[["txn_id", "amount", "settled_amount", "delta", "issue"]].to_string(index=False))

print(f"\n[GAP 2b] Significant amount mismatches (> $0.05): {len(amount_mismatch_df)}")

# =============================================================================
# CELL 11 — Consolidate all exceptions into one report
# =============================================================================

report_frames = []

def add_to_report(df, cols_map):
    """Normalise a gap dataframe into the standard report schema."""
    standard = pd.DataFrame()
    for dest, src in cols_map.items():
        standard[dest] = df[src] if src in df.columns else np.nan
    report_frames.append(standard)

add_to_report(duplicates_df,    {"txn_id":"txn_id", "date":"settlement_date",
                                  "platform_amount":None, "bank_amount":"settled_amount",
                                  "delta":None, "issue":"issue"})
add_to_report(unexpected_df,    {"txn_id":"txn_id", "date":"settlement_date",
                                  "platform_amount":None, "bank_amount":"settled_amount",
                                  "delta":None, "issue":"issue"})
add_to_report(orphan_refunds,   {"txn_id":"txn_id", "date":"txn_date",
                                  "platform_amount":"amount", "bank_amount":None,
                                  "delta":None, "issue":"issue"})
add_to_report(late_df,          {"txn_id":"txn_id", "date":"actual_settlement_date",
                                  "platform_amount":"amount", "bank_amount":None,
                                  "delta":None, "issue":"issue"})
add_to_report(truly_missing_df, {"txn_id":"txn_id", "date":"txn_date",
                                  "platform_amount":"amount", "bank_amount":None,
                                  "delta":None, "issue":"issue"})
add_to_report(rounding_df,      {"txn_id":"txn_id", "date":"txn_date",
                                  "platform_amount":"amount", "bank_amount":"settled_amount",
                                  "delta":"delta", "issue":"issue"})
add_to_report(amount_mismatch_df,{"txn_id":"txn_id","date":"txn_date",
                                  "platform_amount":"amount","bank_amount":"settled_amount",
                                  "delta":"delta","issue":"issue"})

exception_report = pd.concat(report_frames, ignore_index=True)
exception_report = exception_report[
    ["txn_id","date","platform_amount","bank_amount","delta","issue"]
]

print("\n" + "="*72)
print("EXCEPTION REPORT — March 2026 Reconciliation")
print("="*72)
print(exception_report.to_string(index=False))

# =============================================================================
# CELL 12 — Summary statistics
# =============================================================================

summary = (
    exception_report.groupby("issue")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

print("\n" + "="*72)
print("SUMMARY BY ISSUE TYPE")
print("="*72)
print(summary.to_string(index=False))

total_platform = platform_march[platform_march["amount"] > 0]["amount"].sum()
total_bank     = bank_march_deduped["settled_amount"].sum()
net_diff       = round(total_platform - total_bank, 2)

print(f"\nTotal platform captured (Mar): ${total_platform:,.2f}")
print(f"Total bank settled     (Mar): ${total_bank:,.2f}")
print(f"Net difference                : ${net_diff:,.2f}")

# =============================================================================
# CELL 13 — Export artefacts
# =============================================================================

import os
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))  # same folder as the script

exception_report.to_csv(os.path.join(OUTPUT_DIR, "exception_report_march2026.csv"), index=False)
platform_df.to_csv(os.path.join(OUTPUT_DIR, "platform_transactions.csv"), index=False)
bank_df.to_csv(os.path.join(OUTPUT_DIR, "bank_settlements.csv"), index=False)

print(f"\nFiles written to: {OUTPUT_DIR}")
print("  exception_report_march2026.csv")
print("  platform_transactions.csv")
print("  bank_settlements.csv")

# =============================================================================
# CELL 14 — TEST CASES
# =============================================================================

print("\n" + "="*72)
print("TEST CASES")
print("="*72)

def run_test(name, condition, expected=True):
    result = "PASS ✓" if condition == expected else "FAIL ✗"
    print(f"  [{result}]  {name}")

# T1: Late settlements detected
run_test(
    "Late settlements detected",
    len(late_df) == len(LATE_IDS)
)

# T2: Duplicate bank entries detected (2 rows = 1 dupe pair)
run_test(
    "Duplicate bank entries detected",
    len(duplicates_df) == 2
)

# T3: Unexpected bank entry detected
run_test(
    "Unexpected bank entry (ghost) detected",
    GHOST_ID in set(unexpected_df["txn_id"])
)

# T4: Orphan refund detected
run_test(
    "Orphan refund detected",
    ORPHAN_REFUND_ID in set(orphan_refunds["txn_id"])
)

# T5: Rounding differences detected
run_test(
    "Rounding differences detected (3 rows expected)",
    len(rounding_df) == 3
)

# T6: Duplicate bank entries appear EXACTLY twice in report (each pair = 2 rows)
dupe_rows_in_report = exception_report[
    exception_report["issue"] == "DUPLICATE_BANK_ENTRY"
]
run_test(
    "Duplicate bank entries appear exactly twice in report (1 pair = 2 rows)",
    len(dupe_rows_in_report) == 2
)

# T7: Matched clean transactions are NOT in the report (excluding rounding)
exception_non_rounding_ids = set(
    exception_report[~exception_report["issue"].isin(
        ["ROUNDING_DIFFERENCE", "DUPLICATE_BANK_ENTRY"]
    )]["txn_id"]
)
clean_ids = (
    set(matched_df["txn_id"])
    - set(rounding_df["txn_id"])
    - set(amount_mismatch_df["txn_id"])
)
leaked = clean_ids & exception_non_rounding_ids
run_test(
    "Clean matched transactions not flagged as missing/unexpected",
    len(leaked) == 0
)

# T8: Net difference is non-zero (confirms data has gaps)
run_test(
    "Net platform vs bank difference is non-zero",
    net_diff != 0.0
)

print("\nAll tests complete.")