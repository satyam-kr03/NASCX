#!/usr/bin/env python3
"""
Multi-user comparison plots.

Reads comparison_users{N}.csv files from comparison_results_{mode}/
and produces bar charts with number of users on the x-axis:

  1. mean_effective_error_by_users.png
       – Bars: Min CL, Mid CL, Max CL, Model Adaptive
  2. ontime_ratio_by_users.png
       – Same grouping for on-time delivery ratio
  3. delay_by_users.png
       – Same grouping for mean frame delay (ms)
  4. overview_by_users.png
       – All three core metrics side-by-side (sub-plots)

Usage:
    python plot_multiuser.py                          # PCA defaults
    python plot_multiuser.py --mode ae
    python plot_multiuser.py --mode pca --out-dir my_plots
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Style ─────────────────────────────────────────────────────────────────────
PALETTE = {
    "min_cl":  "#4DAF4A",   # green
    "mid_cl":  "#FF7F00",   # orange
    "max_cl":  "#984EA3",   # purple
    "best":    "#2B7BB9",   # steel blue
    "model":   "#E84040",   # vivid red
    "grid":    "#E4E4E4",
    "text":    "#2B2B2B",
}

BAR_COLORS = [
    PALETTE["min_cl"],
    PALETTE["mid_cl"],
    PALETTE["max_cl"],
    PALETTE["model"],
]

BAR_LABELS = [
    "Min CL (static)",
    "Mid CL (static)",
    "Max CL (static)",
    "Model Adaptive",
]

plt.rcParams.update({
    "figure.dpi": 300,  # 300 DPI for print quality
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": PALETTE["grid"],
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "font.family": "serif",  # Matches LaTeX papers well
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#CCCCCC",
    "legend.fontsize": 8,
    "text.color": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
})

SCRIPT_DIR = Path(__file__).parent.resolve()


# ── Data loading ──────────────────────────────────────────────────────────────

def discover_csvs(results_dir: Path) -> dict[int, Path]:
    """Return {num_users: csv_path} for all comparison_users*.csv files."""
    mapping: dict[int, Path] = {}
    for p in sorted(results_dir.glob("comparison_users*.csv")):
        stem = p.stem  # e.g. "comparison_users5"
        try:
            n = int(stem.replace("comparison_users", ""))
            mapping[n] = p
        except ValueError:
            continue
    return dict(sorted(mapping.items()))


def load_all(csv_map: dict[int, Path]) -> pd.DataFrame:
    """Load and concatenate all per-user-count CSVs, adding a num_users column."""
    frames = []
    for n_users, path in csv_map.items():
        df = pd.read_csv(path)
        df["num_users"] = n_users
        frames.append(df)
    df_all = pd.concat(frames, ignore_index=True)
    if "mean_effective_error" in df_all.columns:
        df_all["mean_effective_error"] = np.sqrt(df_all["mean_effective_error"] / (255.0 * 255.0))
    return df_all


# ── Metric aggregation ───────────────────────────────────────────────────────

def aggregate_metric(
    df: pd.DataFrame,
    metric: str,
) -> pd.DataFrame:
    """
    For each num_users value, compute:
      - min_cl_val   : mean metric at the minimum compression level
      - mid_cl_val   : mean metric at the median compression level
      - max_cl_val   : mean metric at the maximum compression level
      - best_static  : mean metric at the best (lowest-error) static CL
      - model_val    : mean metric from model-adaptive rows
      - best_cl      : the CL that yields best static error (for reference)

    Returns a DataFrame indexed by num_users.
    """
    records = []

    for n_users, grp in df.groupby("num_users"):
        static = grp[grp["strategy"] == "static"].copy()
        model  = grp[grp["strategy"] == "model"]

        if static.empty:
            continue

        static["comp_level"] = static["comp_level"].astype(int)
        levels = sorted(static["comp_level"].unique())
        min_cl, max_cl = levels[0], levels[-1]
        mid_cl = levels[len(levels) // 2]

        # per-CL means
        cl_means = static.groupby("comp_level")[metric].mean()

        # best static CL (minimise error, maximise on-time)
        if metric == "on_time_ratio":
            best_cl = int(cl_means.idxmax())
        else:
            best_cl = int(cl_means.idxmin())

        model_val = float(model[metric].mean()) if not model.empty else float("nan")

        records.append({
            "num_users":   n_users,
            "min_cl":      min_cl,
            "mid_cl":      mid_cl,
            "max_cl":      max_cl,
            "min_cl_val":  float(cl_means.get(min_cl, float("nan"))),
            "mid_cl_val":  float(cl_means.get(mid_cl, float("nan"))),
            "max_cl_val":  float(cl_means.get(max_cl, float("nan"))),
            "best_cl":     best_cl,
            "best_static": float(cl_means.get(best_cl, float("nan"))),
            "model_val":   model_val,
        })

    return pd.DataFrame(records).set_index("num_users")


# ── Plotting helpers ──────────────────────────────────────────────────────────

def _grouped_bar(
    ax: plt.Axes,
    user_counts: list[int],
    values: np.ndarray,         # shape (n_groups, 4)  — one col per bar category
    ylabel: str,
    title: str,
    agg_df: pd.DataFrame,       # for annotating CL numbers
    ylim: tuple | None = None,
    fmt: str = ".4g",
):
    """Draw a grouped bar chart on *ax*."""
    n_groups = len(user_counts)
    n_bars = values.shape[1]
    width = 0.20
    x = np.arange(n_groups) * 1.25

    HATCHES = ['//', '\\\\', 'xx', '']  # hatch patterns for distinguishing bars in B&W

    for j in range(n_bars):
        offset = (j - n_bars / 2 + 0.5) * width
        bars = ax.bar(
            x + offset, values[:, j], width,
            color=BAR_COLORS[j], label=BAR_LABELS[j], alpha=0.88,
            edgecolor="white", linewidth=0.5, hatch=HATCHES[j % len(HATCHES)],
        )

    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in user_counts])
    ax.set_xlabel("Number of Users")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(ylim)
    else:
        bottom, top = ax.get_ylim()
        ax.set_ylim(bottom, top + (top - bottom) * 0.35)
    ax.legend(loc="upper center", ncol=2, fontsize=7)


def _build_values(agg: pd.DataFrame) -> np.ndarray:
    """Stack the four bar columns into an (n, 4) array."""
    return np.column_stack([
        agg["min_cl_val"].values,
        agg["mid_cl_val"].values,
        agg["max_cl_val"].values,
        agg["model_val"].values,
    ])


# ── Individual figure functions ───────────────────────────────────────────────

def fig_metric_by_users(
    full_df: pd.DataFrame,
    metric: str,
    ylabel: str,
    title: str,
    out: Path,
    ylim: tuple | None = None,
    fmt: str = ".4g",
):
    agg = aggregate_metric(full_df, metric)
    user_counts = list(agg.index)
    vals = _build_values(agg)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _grouped_bar(ax, user_counts, vals, ylabel, title, agg, ylim=ylim, fmt=fmt)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    fig.set_size_inches(5.0, 3.5)
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig_pct_improvement(full_df: pd.DataFrame, out: Path, metric: str = "mean_effective_error"):
    """Bar chart: Model improvement (%) over best static, per user count."""
    agg = aggregate_metric(full_df, metric)
    user_counts = list(agg.index)
    pct = (
        (agg["best_static"] - agg["model_val"]) / agg["best_static"] * 100
    ).values

    fig, ax = plt.subplots(figsize=(max(7, len(user_counts) * 1.2), 5))
    colors = [PALETTE["model"] if v >= 0 else "#888888" for v in pct]
    bars = ax.bar(range(len(user_counts)), pct, color=colors, alpha=0.85,
                  edgecolor="white", linewidth=0.5)

    for i, (bar, v) in enumerate(zip(bars, pct)):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + (0.5 if v >= 0 else -1.5),
            f"{v:+.2f}%", ha="center", va="bottom" if v >= 0 else "top",
            fontsize=9, fontweight="bold",
        )

    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_xticks(range(len(user_counts)))
    ax.set_xticklabels([str(u) for u in user_counts])
    ax.set_xlabel("Number of Users")
    ax.set_ylabel("Improvement (%)")
    ax.set_title("Model Adaptive Improvement over Best Static (Mean Effective Error)")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def fig_overview_by_users(full_df: pd.DataFrame, out: Path):
    """Three sub-plot overview: error, on-time ratio, delay — by user count."""
    metrics = [
        ("mean_effective_error", "Mean Effective Error", None, ".4g"),
        ("on_time_ratio",        "On-Time Ratio",       (0, 1.35), ".3f"),
        ("mean_delay_ms",        "Mean Delay (ms)",      None, ".2f"),
    ]
    # keep only metrics present
    metrics = [
        (m, l, yl, f) for m, l, yl, f in metrics
        if m in full_df.columns
    ]
    n = len(metrics)
    if n == 0:
        return

    # Scales properly across IEEE standard 7.16" double-column span
    fig, axes = plt.subplots(1, n, figsize=(7.16, 2.8), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, (metric, ylabel, ylim, fmt) in zip(axes, metrics):
        agg = aggregate_metric(full_df, metric)
        user_counts = list(agg.index)
        vals = _build_values(agg)
        _grouped_bar(ax, user_counts, vals, ylabel, ylabel, agg, ylim=ylim, fmt=fmt)

    fig.suptitle("Model Adaptive vs Static Compression — Multi-User Overview",
                 y=1.02, fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    fig.set_size_inches(2.35 * n, 3.5)
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Plot multi-user comparison bar charts"
    )
    parser.add_argument("--mode", choices=["pca", "ae"], default="pca",
                        help="Which results set to plot (pca or ae)")
    parser.add_argument("--results-dir", type=Path,
                        help="Directory containing comparison_users*.csv "
                             "(default: comparison_results_{mode}/)")
    parser.add_argument("--out-dir", type=Path,
                        help="Output directory for plots "
                             "(default: plots_{mode}_multiuser/)")
    args = parser.parse_args()

    mode = args.mode
    results_dir = args.results_dir or (SCRIPT_DIR / f"comparison_results_{mode}")
    out_dir = args.out_dir or (SCRIPT_DIR / f"plots_{mode}_multiuser")

    csv_map = discover_csvs(results_dir)
    if not csv_map:
        print(f"[ERROR] No comparison_users*.csv files found in {results_dir}")
        print("  Run run_multiuser_sweep.sh first.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(csv_map)} user-count CSVs: "
          f"{list(csv_map.keys())}")
    full_df = load_all(csv_map)
    print(f"Total rows: {len(full_df)}")
    print(f"Generating plots → {out_dir}/\n")

    # 1. Mean effective error
    fig_metric_by_users(
        full_df,
        metric="mean_effective_error",
        ylabel="Mean Effective Error",
        title="Mean Effective Error by Number of Users",
        out=out_dir / "mean_effective_error_by_users.pdf",
    )

    # 2. On-time ratio
    if "on_time_ratio" in full_df.columns:
        fig_metric_by_users(
            full_df,
            metric="on_time_ratio",
            ylabel="On-Time Frame Ratio",
            title="On-Time Ratio by Number of Users",
            out=out_dir / "ontime_ratio_by_users.pdf",
            ylim=(0, 1.35),
            fmt=".3f",
        )

    # 3. Mean delay
    if "mean_delay_ms" in full_df.columns:
        fig_metric_by_users(
            full_df,
            metric="mean_delay_ms",
            ylabel="Mean Delay (ms)",
            title="Mean Frame Delay by Number of Users",
            out=out_dir / "delay_by_users.pdf",
            fmt=".2f",
        )

    # 4. Overview (3 sub-plots)
    fig_overview_by_users(
        full_df,
        out=out_dir / "overview_by_users.pdf",
    )

    print(f"\nDone. {len(list(out_dir.glob('*.pdf')))} PDF(s) in {out_dir}/")


if __name__ == "__main__":
    main()
