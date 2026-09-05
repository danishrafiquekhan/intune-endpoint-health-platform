#!/usr/bin/env python3
"""Duplicate asset reconciliation — LegacyCMDB vs Intune device records.

Based on a real cleanup: LegacyCMDB (the legacy asset-management tool) and Intune both had
records for the same physical devices, but they'd drifted apart — a device
re-enrolled and got a new LegacyCMDB asset ID while keeping the same serial
number, or someone typed the device name differently between the two systems
("LAPTOP-JS4021" vs "laptop-js4021" vs "Laptop_JS4021"). At a few hundred
devices this is genuinely tedious to reconcile by eye in a spreadsheet, and
eyeballing a sorted column misses anything that isn't adjacent alphabetically.

This script doesn't call either system's API — it works off an exported CSV
(that's how I actually had to do it; API access to LegacyCMDB wasn't something
I had a token for at the time). It reads one CSV containing rows from both
sources, groups rows that look like the same physical device, and writes a
reconciliation report: which records are likely duplicates, why the script
thinks so, and which one it suggests keeping as the canonical record.

Matching logic (see `find_duplicate_groups`):
  1. Exact serial number match (case/whitespace-normalized) — this is the
     strong signal. A serial number is supposed to be unique to one physical
     device, so two rows with the same one are almost certainly the same
     machine under two asset records, regardless of what the device name
     says.
  2. No serial match, but a normalized device name match (case-insensitive,
     punctuation/whitespace collapsed) — weaker signal, flagged as
     lower-confidence because device names get reused or reassigned in ways
     serial numbers don't.
  3. Fuzzy device-name similarity via difflib.SequenceMatcher above a
     threshold, for names that are close but not identical after
     normalization (typos, truncation, a stray character) — lowest
     confidence, always needs a human look.

Deliberately stdlib-only for the matching (difflib), plus pandas for reading/
writing the CSV/report tables — didn't want to pull in a fuzzy-matching
dependency (e.g. rapidfuzz) for something difflib already does well enough
at this data size. See the requirements.txt entry for pandas.

Usage:
    python3 asset_reconciliation.py sample_device_records.csv
    python3 asset_reconciliation.py sample_device_records.csv --out report.csv

I've run this against the synthetic sample CSV in this repo and checked the
output by hand — every seeded duplicate pair got flagged, and the negative
examples didn't. I have NOT run it against a real LegacyCMDB/Intune export;
the version I built this from doesn't leave the work laptop it was built on,
so this is a rebuild against fake data, not the original output.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass, field

import pandas as pd

NAME_FUZZY_THRESHOLD = 0.82  # difflib ratio; below this we don't even flag as low-confidence


def normalize_serial(serial: str) -> str:
    if not isinstance(serial, str):
        return ""
    return re.sub(r"[\s\-]", "", serial).strip().upper()


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    # collapse case, underscores/dashes/extra whitespace so
    # "LAPTOP-JS4021", "laptop_js4021", "Laptop  JS4021" all normalize the same
    collapsed = re.sub(r"[\s_\-]+", "", name.strip().lower())
    return collapsed


@dataclass
class DuplicateGroup:
    row_indices: list[int]
    reason: str
    confidence: str
    detail: str
    canonical_index: int = field(default=-1)


def choose_canonical(df: pd.DataFrame, row_indices: list[int]) -> int:
    """Pick a suggested canonical record out of a duplicate group.

    Heuristic, not authoritative: prefer the row with the most recently seen
    'last_check_in' date (most likely to reflect current reality), and break
    ties by preferring the row sourced from Intune over LegacyCMDB, since
    Intune's check-in data tends to be fresher than a manually-updated CMDB
    entry. This is a starting suggestion for the human doing the merge, not
    a rule to apply blindly — see the limitations note in the docs.
    """
    candidates = df.loc[row_indices].copy()
    candidates["_checkin_parsed"] = pd.to_datetime(candidates["last_check_in"], errors="coerce")
    candidates = candidates.sort_values(
        by=["_checkin_parsed", "source"],
        ascending=[False, True],  # newest check-in first; 'Intune' sorts before 'LegacyCMDB' alphabetically as a tiebreak nudge
    )
    return candidates.index[0]


def find_duplicate_groups(df: pd.DataFrame) -> list[DuplicateGroup]:
    df = df.copy()
    df["_norm_serial"] = df["serial_number"].apply(normalize_serial)
    df["_norm_name"] = df["device_name"].apply(normalize_name)

    groups: list[DuplicateGroup] = []
    claimed: set[int] = set()

    # Pass 1: exact serial number match (excluding blank serials)
    serial_groups = df[df["_norm_serial"] != ""].groupby("_norm_serial").groups
    for serial, idx in serial_groups.items():
        idx = list(idx)
        if len(idx) > 1:
            names = df.loc[idx, "device_name"].tolist()
            groups.append(
                DuplicateGroup(
                    row_indices=idx,
                    reason="same serial number",
                    confidence="high",
                    detail=f"serial '{serial}' shared across names {names}",
                )
            )
            claimed.update(idx)

    # Pass 2: exact normalized name match among rows not already claimed by a serial match
    remaining = df.loc[~df.index.isin(claimed)]
    name_groups = remaining[remaining["_norm_name"] != ""].groupby("_norm_name").groups
    for norm_name, idx in name_groups.items():
        idx = list(idx)
        if len(idx) > 1:
            raw_names = df.loc[idx, "device_name"].tolist()
            groups.append(
                DuplicateGroup(
                    row_indices=idx,
                    reason="same device name (case/formatting variant)",
                    confidence="medium",
                    detail=f"names {raw_names} normalize to '{norm_name}'",
                )
            )
            claimed.update(idx)

    # Pass 3: fuzzy name similarity among whatever's still unclaimed
    remaining_idx = [i for i in df.index if i not in claimed]
    seen_in_fuzzy: set[int] = set()
    for i in remaining_idx:
        if i in seen_in_fuzzy:
            continue
        name_i = df.loc[i, "_norm_name"]
        if not name_i:
            continue
        matches = [i]
        for j in remaining_idx:
            if j <= i or j in seen_in_fuzzy:
                continue
            name_j = df.loc[j, "_norm_name"]
            if not name_j:
                continue
            ratio = difflib.SequenceMatcher(None, name_i, name_j).ratio()
            if ratio >= NAME_FUZZY_THRESHOLD:
                matches.append(j)
        if len(matches) > 1:
            raw_names = df.loc[matches, "device_name"].tolist()
            groups.append(
                DuplicateGroup(
                    row_indices=matches,
                    reason="fuzzy name similarity",
                    confidence="low",
                    detail=f"names {raw_names} are similar but not identical after normalization "
                    f"(ratio >= {NAME_FUZZY_THRESHOLD})",
                )
            )
            seen_in_fuzzy.update(matches)

    for g in groups:
        g.canonical_index = choose_canonical(df, g.row_indices)

    return groups


def build_report(df: pd.DataFrame, groups: list[DuplicateGroup]) -> pd.DataFrame:
    rows = []
    for gi, g in enumerate(groups, start=1):
        for idx in g.row_indices:
            record = df.loc[idx]
            rows.append(
                {
                    "group_id": gi,
                    "confidence": g.confidence,
                    "match_reason": g.reason,
                    "match_detail": g.detail,
                    "asset_id": record.get("asset_id"),
                    "source": record.get("source"),
                    "device_name": record.get("device_name"),
                    "serial_number": record.get("serial_number"),
                    "last_check_in": record.get("last_check_in"),
                    "suggested_canonical": idx == g.canonical_index,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", help="CSV of device records (see sample_device_records.csv for expected columns)")
    parser.add_argument("--out", default=None, help="Where to write the reconciliation report CSV (default: print to stdout only)")
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.input_csv)
    except FileNotFoundError:
        print(f"Input file not found: {args.input_csv}", file=sys.stderr)
        sys.exit(1)

    required_cols = {"asset_id", "source", "device_name", "serial_number", "last_check_in"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"Input CSV is missing required column(s): {sorted(missing)}", file=sys.stderr)
        sys.exit(1)

    total_records = len(df)
    groups = find_duplicate_groups(df)
    flagged_records = sum(len(g.row_indices) for g in groups)
    report_df = build_report(df, groups)

    print(f"Input records: {total_records}")
    print(f"Duplicate groups found: {len(groups)}")
    print(f"Records flagged as part of a duplicate group: {flagged_records}")
    print(f"Records with no likely duplicate: {total_records - flagged_records}")
    print(
        f"After reconciliation (one canonical record kept per group): "
        f"{total_records - flagged_records + len(groups)} record(s) would remain\n"
    )

    by_confidence = report_df.groupby("group_id").first()["confidence"].value_counts() if not report_df.empty else {}
    for level in ("high", "medium", "low"):
        count = by_confidence.get(level, 0) if hasattr(by_confidence, "get") else 0
        print(f"  {level} confidence groups: {count}")

    if args.out:
        report_df.to_csv(args.out, index=False)
        print(f"\nFull report written to {args.out}")
    else:
        print("\n--- report (pass --out to write this to a file) ---")
        if report_df.empty:
            print("No duplicate groups found.")
        else:
            print(report_df.to_string(index=False))

    print(
        "\nReminder: this is a triage aid, not an auto-merge tool. 'low' and "
        "'medium' confidence groups especially need a human to confirm before "
        "anything gets merged — see docs/asset-reconciliation.md for the "
        "false-positive risk this doesn't protect against on its own."
    )


if __name__ == "__main__":
    main()
