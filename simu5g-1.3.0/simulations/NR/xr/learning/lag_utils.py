"""
lag_utils.py — Lagged delay feature utilities.

Adds a ``prev_user{i}_delay_ms`` column to the dataset by shifting each
user's ``delay_ms`` within each sequential simulation run (identified by
the ``repetition`` column).  Rows where the previous frame is unavailable
(first frame of each run, or after a gap from a dropped frame) are dropped.

Import into ``classifier.py``::

    from lag_utils import add_lagged_delay
"""

import pandas as pd


def add_lagged_delay(df: pd.DataFrame, num_users: int) -> pd.DataFrame:
    """Lag each user's delay_ms by one frame within each simulation run.

    Parameters
    ----------
    df : DataFrame
        Filtered to one ``num_users`` value.  Must contain ``repetition``,
        ``frameNumber``, and ``user{i}_delay_ms`` columns.
    num_users : int
        Number of users in this configuration.

    Returns
    -------
    DataFrame
        With added ``prev_user{i}_delay_ms`` columns.  First-frame rows
        and gap rows (where the previous frame was lost) are dropped.
    """
    delay_cols = [f"user{i}_delay_ms" for i in range(num_users)]

    # Sort so shift(1) is meaningful
    df = df.sort_values(["repetition", "frameNumber"]).reset_index(drop=True)
    before = len(df)

    # Within each repetition, lag delay by one frame
    for col in delay_cols:
        df[f"prev_{col}"] = df.groupby("repetition")[col].shift(1)

    # Also lag frameNumber to detect gaps
    df["prev_frameNumber"] = df.groupby("repetition")["frameNumber"].shift(1)

    prev_cols = [f"prev_{c}" for c in delay_cols]

    # Drop rows where:
    #   1. prev frame doesn't exist (first frame of each run → NaN)
    #   2. gap between current and previous frame > 1 (dropped frame)
    df = df.dropna(subset=prev_cols).copy()
    gap = df["frameNumber"] - df["prev_frameNumber"]
    df = df[gap == 1].copy()
    df = df.drop(columns=["prev_frameNumber"]).reset_index(drop=True)

    n_dropped = before - len(df)
    if n_dropped > 0:
        import logging
        logging.getLogger(__name__).debug(
            f"add_lagged_delay: dropped {n_dropped} rows "
            f"(first-frame + gap rows)"
        )

    return df