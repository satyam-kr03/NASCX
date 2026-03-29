#!/usr/bin/env python3
"""
Simple utility for cleaning datasets in the XR PCA simulations folder.

Currently this script removes any rows where one or more of the
``*_delay_ms`` columns contain a negative value.  After filtering, it
reports whether any rows still contain a CQI value of ``0`` (which can
serve as a sanity check) and writes the cleaned frame to a new file.

Usage::

    python clean_dataset.py \
        path/to/random_cl_dataset.csv \
        path/to/random_cl_dataset_clean.csv

python clean_dataset.py pca/dataset.csv pca/dataset.csv

The output file will have the same header and numeric precision as the
input, with the offending rows dropped.
"""

import argparse
import sys

import pandas as pd

def clean(input_path: str, output_path: str) -> None:
    df = pd.read_csv(input_path)

    # identify the delay columns (any column name containing "delay_ms")
    delay_cols = [col for col in df.columns if "delay_ms" in col]
    if not delay_cols:
        print("no delay columns found in input", file=sys.stderr)

    # drop rows where any *active* user's delay column is negative.
    # rows with fewer than 10 users have NaN in unused user slots;
    # NaN >= 0 evaluates to False, so a blanket check would wrongly
    # discard every row whose num_users < 10.  Instead, only inspect
    # delay columns for users 0 .. num_users-1.
    if "num_users" in df.columns:
        def _active_delays_ok(row):
            n = int(row["num_users"])
            for u in range(n):
                col = f"user{u}_delay_ms"
                if col in row.index and row[col] < 0:
                    return False
            return True

        mask = df.apply(_active_delays_ok, axis=1)
    else:
        # fallback: no num_users column — check all, treating NaN as OK
        mask = (df[delay_cols].fillna(0) >= 0).all(axis=1)

    before = len(df)
    df = df[mask]
    after = len(df)
    removed = before - after
    print(f"removed {removed} rows with negative delays")

    # sanity check: make sure there are no CQI == 0 rows left
    cqi_cols = [col for col in df.columns if col.endswith("_cqi")]
    if cqi_cols:
        zeros = (df[cqi_cols] == 0).any(axis=1)
        if zeros.any():
            print(
                f"warning: {zeros.sum()} rows still contain a CQI of 0",
                file=sys.stderr,
            )
        else:
            print("verification passed: no CQI=0 rows present")
    else:
        print("no CQI columns found for verification")

    # write cleaned file
    df.to_csv(output_path, index=False)
    print(f"cleaned dataset written to {output_path}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Remove rows with negative delays from a CSV dataset",
    )
    parser.add_argument(
        "input",
        help="path to the input CSV file",
    )
    parser.add_argument(
        "output",
        help="path where the cleaned CSV should be written",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    clean(args.input, args.output)
