"""
lag_utils.py
Utility functions for adding lagged delay features to the dataset.
Import these into classifier.py.

Requires the CSV to have a 'repetition' column. Each (num_users, repetition)
pair is one sequential simulation run — prev_delay is only lagged within a run,
never across runs.
"""

import pandas as pd


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
    before = len(df)
    df = df.dropna(subset=prev_cols).copy()
    gap = df["frameNumber"] - df["prev_frameNumber"]
    df = df[gap == 1].copy()
    df = df.drop(columns=["prev_frameNumber"]).reset_index(drop=True)

    n_dropped = before - len(df)
    return df