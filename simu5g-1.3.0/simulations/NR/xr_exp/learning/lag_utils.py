"""
lag_utils.py
Utility functions for adding lagged delay features to the dataset.
Import these into compression_policy.py and classifier.py.

Requires the CSV to have a 'repetition' column (added now successfully). Each (num_users, repetition) pair is one sequential
simulation run — prev_delay is only lagged within a run, never across runs.
"""

import pandas as pd
import numpy as np


def add_lagged_delay(df: pd.DataFrame, num_users: int) -> pd.DataFrame:
    """
    For each simulation run (identified by 'repetition'), lag each user's
    delay_ms by one frame and add it as prev_delay_ms.

    Rows where the previous frame is unavailable (first frame of each run,
    or after a gap from a dropped frame) are dropped.

    Parameters
    ----------
    df        : DataFrame filtered to one num_users value, must have
                'repetition', 'frameNumber', and user{i}_delay_ms columns.
    num_users : number of users in this configuration.

    Returns
    -------
    DataFrame with added prev_user{i}_delay_ms columns, first-frame rows
    dropped, gap rows dropped.
    """
    delay_cols = [f"user{i}_delay_ms" for i in range(num_users)]

    # Sort so shift(1) is meaningful
    df = (df.sort_values(["repetition", "frameNumber"])
            .reset_index(drop=True))

    # Within each repetition, lag delay by one frame
    for col in delay_cols:
        df[f"prev_{col}"] = (
            df.groupby("repetition")[col]
              .shift(1)
        )

    # Also lag frameNumber to detect gaps
    df["prev_frameNumber"] = (
        df.groupby("repetition")["frameNumber"]
          .shift(1)
    )

    prev_cols = [f"prev_{c}" for c in delay_cols]

    # Drop rows where:
    #   1. prev frame doesn't exist (first frame of each run → NaN)
    #   2. gap between current and previous frame > 1 (dropped frame between them)
    df = df.dropna(subset=prev_cols).copy()
    gap = df["frameNumber"] - df["prev_frameNumber"]
    df = df[gap == 1].copy()
    df = df.drop(columns=["prev_frameNumber"]).reset_index(drop=True)

    n_dropped = len(df) - len(df)  # already filtered above
    return df


def check_lag_quality(df_lagged: pd.DataFrame, num_users: int):
    """
    Print correlation of prev_delay with components for each user.
    Call this after add_lagged_delay to verify the feature is informative.
    """
    print(f"  Lagged delay feature quality ({len(df_lagged):,} rows after lag):")
    for i in range(num_users):
        c = (df_lagged[[f"prev_user{i}_delay_ms",
                        f"user{i}_components"]]
               .corr().iloc[0, 1])
        bar  = "█" * max(0, int(abs(c) * 50))
        sign = "+" if c >= 0 else "-"
        print(f"    prev_delay_u{i} ↔ components_u{i}: {sign}{abs(c):.3f}  {bar}")

    # Within-state consistency with binned prev_delay
    err_cols   = [f"user{i}_effectiveError" for i in range(num_users)]
    state_cols = []
    for i in range(num_users):
        state_cols += [f"user{i}_cqi", f"user{i}_frame_rate"]

    df_lagged = df_lagged.copy()
    df_lagged["total_error"] = df_lagged[err_cols].sum(axis=1)

    # Bin prev_delay to 2ms buckets
    for i in range(num_users):
        col = f"prev_user{i}_delay_ms"
        df_lagged[f"{col}_bin"] = (df_lagged[col] / 2).round() * 2

    state_cols_ext = state_cols + [f"prev_user{i}_delay_ms_bin"
                                   for i in range(num_users)]

    opt_idx = df_lagged.groupby(state_cols_ext)["total_error"].idxmin()
    opt_df  = df_lagged.loc[opt_idx]
    print(f"  Unique (cqi, fps, prev_delay_bin) states: {len(opt_df):,}")

    for i in range(num_users):
        col   = f"user{i}_components"
        stats = df_lagged.groupby(state_cols_ext)[col].agg(["nunique","count"])
        multi = stats[stats["count"] > 1]
        if len(multi) == 0:
            print(f"  user{i}: no multi-row states"); continue
        always_same = (multi["nunique"] == 1).mean() * 100
        avg_unique  = multi["nunique"].mean()
        print(f"  user{i}: {always_same:.1f}% of states → same k  "
              f"(avg {avg_unique:.1f} distinct k per state)")