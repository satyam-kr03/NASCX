#!/usr/bin/env python3
"""
Visualisation script for comparison_results/comparison.csv.

Produces six figures saved to plots/:
  1. effective_error_vs_cl.png   – mean effective error vs compression level
                                   (static curve + model horizontal band)
  2. ontime_ratio_vs_cl.png      – on-time frame ratio vs compression level
  3. delay_vs_cl.png             – mean delay vs compression level
  4. per_user_error.png          – per-user effective error: model vs best static
  5. per_video_error.png         – per-video aggregated effective error
  6. model_vs_static_bar.png     – grouped bar: model vs every static level
                                   (for all three metrics side-by-side)

Usage:
    python plot_comparison.py [--csv PATH] [--out-dir DIR]
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
    "model":  "#E84040",   # vivid red for model/adaptive
    "static": "#2B7BB9",   # steel blue for static
    "band":   "#F5AAAA",   # light red fill for model CI band
    "grid":   "#E4E4E4",
    "text":   "#2B2B2B",
}

plt.rcParams.update({
    "figure.dpi": 150,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": PALETTE["grid"],
    "grid.linewidth": 0.6,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "text.color": PALETTE["text"],
    "axes.labelcolor": PALETTE["text"],
    "xtick.color": PALETTE["text"],
    "ytick.color": PALETTE["text"],
})

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_CSV  = SCRIPT_DIR / "comparison_results" / "comparison.csv"
DEFAULT_PLOTS = SCRIPT_DIR / "plots"


# ── Data helpers ──────────────────────────────────────────────────────────────

def load(csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    """Return (model_df, static_df, sorted static comp levels)."""
    df = pd.read_csv(csv_path)

    # comp_level is stored as "adaptive" (str) or integer-like value
    model_df  = df[df["strategy"] == "model"].copy()
    static_df = df[df["strategy"] == "static"].copy()
    static_df["comp_level"] = static_df["comp_level"].astype(int)
    levels = sorted(static_df["comp_level"].unique())
    return model_df, static_df, levels


def static_agg(static_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Aggregate a metric over users, grouped by comp_level."""
    return (
        static_df.groupby("comp_level")[metric]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
        .sort_values("comp_level")
    )


def model_stats(model_df: pd.DataFrame, metric: str) -> tuple[float, float, float]:
    """Return (mean, std, sem) of a metric across model rows."""
    vals = model_df[metric].dropna()
    return float(vals.mean()), float(vals.std()), float(vals.sem())


def best_static(static_df: pd.DataFrame, metric: str, minimize: bool = True) -> int:
    """Return the comp_level with the best aggregate metric."""
    agg = static_agg(static_df, metric)
    col = "mean"
    return int(agg.loc[agg[col].idxmin() if minimize else agg[col].idxmax(), "comp_level"])


# ── Figure 1 – Effective error vs CL ─────────────────────────────────────────

def fig_error_vs_cl(model_df, static_df, out: Path):
    agg = static_agg(static_df, "mean_effective_error")
    m_mean, m_std, _ = model_stats(model_df, "mean_effective_error")

    fig, ax = plt.subplots(figsize=(9, 5))

    # static curve with shaded ±1 σ
    ax.fill_between(
        agg["comp_level"],
        agg["mean"] - agg["std"],
        agg["mean"] + agg["std"],
        color=PALETTE["static"], alpha=0.15, label="Static ±1 σ",
    )
    ax.plot(
        agg["comp_level"], agg["mean"],
        color=PALETTE["static"], linewidth=2, marker="o", markersize=5,
        label="Static (mean across users)",
    )

    # model horizontal band
    ax.axhspan(
        m_mean - m_std, m_mean + m_std,
        color=PALETTE["band"], alpha=0.55, label="Model ±1 σ",
    )
    ax.axhline(m_mean, color=PALETTE["model"], linewidth=2.0,
               linestyle="--", label=f"Model adaptive  (μ={m_mean:.4f})")

    # annotate best static
    bs = best_static(static_df, "mean_effective_error")
    bs_val = float(agg.loc[agg["comp_level"] == bs, "mean"].iloc[0])
    ax.annotate(
        f"Best static\nCL={bs}  ({bs_val:.4f})",
        xy=(bs, bs_val), xytext=(bs + 20, bs_val + (m_mean - bs_val) * 0.35),
        fontsize=9, color=PALETTE["static"],
        arrowprops=dict(arrowstyle="->", color=PALETTE["static"], lw=1.2),
    )

    ax.set_xlabel("Compression Level")
    ax.set_ylabel("Mean Effective Error")
    ax.set_title("Effective Error vs Compression Level")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Figure 2 – On-time ratio vs CL ───────────────────────────────────────────

def fig_ontime_vs_cl(model_df, static_df, out: Path):
    metric = "on_time_ratio"
    if metric not in static_df.columns:
        print(f"  [SKIP] Column '{metric}' not found.")
        return

    agg = static_agg(static_df, metric)
    m_mean, m_std, _ = model_stats(model_df, metric)

    fig, ax = plt.subplots(figsize=(9, 5))

    ax.fill_between(
        agg["comp_level"],
        (agg["mean"] - agg["std"]).clip(0, 1),
        (agg["mean"] + agg["std"]).clip(0, 1),
        color=PALETTE["static"], alpha=0.15,
    )
    ax.plot(
        agg["comp_level"], agg["mean"],
        color=PALETTE["static"], linewidth=2, marker="o", markersize=5,
        label="Static (mean)",
    )
    ax.axhspan(
        max(0, m_mean - m_std), min(1, m_mean + m_std),
        color=PALETTE["band"], alpha=0.55, label="Model ±1 σ",
    )
    ax.axhline(m_mean, color=PALETTE["model"], linewidth=2.0,
               linestyle="--", label=f"Model adaptive  (μ={m_mean:.3f})")

    ax.set_xlabel("Compression Level")
    ax.set_ylabel("On-Time Frame Ratio")
    ax.set_title("On-Time Ratio vs Compression Level")
    ax.set_ylim(0, 1.05)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Figure 3 – Mean delay vs CL ──────────────────────────────────────────────

def fig_delay_vs_cl(model_df, static_df, out: Path):
    metric = "mean_delay_ms"
    if metric not in static_df.columns:
        print(f"  [SKIP] Column '{metric}' not found.")
        return

    agg = static_agg(static_df, metric)
    m_mean, m_std, _ = model_stats(model_df, metric)

    fig, ax = plt.subplots(figsize=(9, 5))

    ax.fill_between(
        agg["comp_level"],
        agg["mean"] - agg["std"],
        agg["mean"] + agg["std"],
        color=PALETTE["static"], alpha=0.15,
    )
    ax.plot(
        agg["comp_level"], agg["mean"],
        color=PALETTE["static"], linewidth=2, marker="o", markersize=5,
        label="Static (mean)",
    )
    ax.axhspan(
        m_mean - m_std, m_mean + m_std,
        color=PALETTE["band"], alpha=0.55, label="Model ±1 σ",
    )
    ax.axhline(m_mean, color=PALETTE["model"], linewidth=2.0,
               linestyle="--", label=f"Model adaptive  (μ={m_mean:.2f} ms)")

    ax.set_xlabel("Compression Level")
    ax.set_ylabel("Mean Delay (ms)")
    ax.set_title("Mean Frame Delay vs Compression Level")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Figure 4 – Per-user error: model vs best static ──────────────────────────

def fig_per_user_error(model_df, static_df, out: Path):
    bs_cl = best_static(static_df, "mean_effective_error")
    bs_df = static_df[static_df["comp_level"] == bs_cl]

    users = sorted(model_df["user"].unique())
    model_vals  = [model_df.loc[model_df["user"] == u, "mean_effective_error"].mean() for u in users]
    static_vals = [bs_df.loc[bs_df["user"] == u, "mean_effective_error"].mean() if u in bs_df["user"].values else float("nan") for u in users]

    x = np.arange(len(users))
    w = 0.35

    fig, ax = plt.subplots(figsize=(max(7, len(users) * 1.2), 5))
    bars_s = ax.bar(x - w / 2, static_vals, w,
                    color=PALETTE["static"], label=f"Best static (CL={bs_cl})", alpha=0.85)
    bars_m = ax.bar(x + w / 2, model_vals, w,
                    color=PALETTE["model"], label="Model adaptive", alpha=0.85)

    # value labels
    for bar in list(bars_s) + list(bars_m):
        h = bar.get_height()
        if np.isfinite(h):
            ax.text(bar.get_x() + bar.get_width() / 2, h * 1.012,
                    f"{h:.4f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("User ID")
    ax.set_ylabel("Mean Effective Error")
    ax.set_title("Per-User Effective Error: Model vs Best Static")
    ax.set_xticks(x)
    ax.set_xticklabels([f"User {u}" for u in users])
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Figure 5 – Per-video aggregated error ────────────────────────────────────

def fig_per_video_error(model_df, static_df, out: Path):
    bs_cl = best_static(static_df, "mean_effective_error")
    bs_df = static_df[static_df["comp_level"] == bs_cl]

    model_vid  = model_df.groupby("video")["mean_effective_error"].mean().sort_index()
    static_vid = bs_df.groupby("video")["mean_effective_error"].mean().reindex(model_vid.index)

    videos = list(model_vid.index)
    x = np.arange(len(videos))
    w = 0.35

    fig, ax = plt.subplots(figsize=(max(8, len(videos) * 1.5), 5))
    ax.bar(x - w / 2, static_vid.values, w,
           color=PALETTE["static"], label=f"Best static (CL={bs_cl})", alpha=0.85)
    ax.bar(x + w / 2, model_vid.values, w,
           color=PALETTE["model"], label="Model adaptive", alpha=0.85)

    ax.set_xlabel("Video")
    ax.set_ylabel("Mean Effective Error")
    ax.set_title("Per-Video Effective Error: Model vs Best Static")
    ax.set_xticks(x)
    ax.set_xticklabels(videos, rotation=20, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Figure 6 – Three-metric overview (subplots) ──────────────────────────────

def fig_overview(model_df, static_df, levels, out: Path):
    metrics = [
        ("mean_effective_error", "Mean Effective Error", True),
        ("on_time_ratio",        "On-Time Ratio",        False),
        ("mean_delay_ms",        "Mean Delay (ms)",      True),
    ]
    # keep only metrics that exist
    metrics = [(m, l, lo) for m, l, lo in metrics
               if m in static_df.columns and m in model_df.columns]

    n = len(metrics)
    if n == 0:
        return

    fig, axes = plt.subplots(1, n, figsize=(6 * n, 5), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, (metric, label, minimize) in zip(axes, metrics):
        agg = static_agg(static_df, metric)
        m_mean, m_std, _ = model_stats(model_df, metric)

        x = np.arange(len(levels))
        s_vals = [float(agg.loc[agg["comp_level"] == cl, "mean"].iloc[0])
                  if cl in agg["comp_level"].values else float("nan")
                  for cl in levels]
        s_stds = [float(agg.loc[agg["comp_level"] == cl, "std"].iloc[0])
                  if cl in agg["comp_level"].values else 0.0
                  for cl in levels]

        ax.bar(x, s_vals, color=PALETTE["static"], alpha=0.75,
               yerr=s_stds, capsize=3, label="Static levels",
               error_kw={"elinewidth": 1, "ecolor": "#888"})
        ax.axhline(m_mean, color=PALETTE["model"], linewidth=2,
                   linestyle="--", label=f"Model  (μ={m_mean:.4g})")
        ax.axhspan(
            m_mean - m_std, m_mean + m_std,
            color=PALETTE["band"], alpha=0.45,
        )

        ax.set_xticks(x[::2])
        ax.set_xticklabels([str(levels[i]) for i in range(0, len(levels), 2)],
                           rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("Compression Level")
        ax.set_ylabel(label)
        ax.set_title(label)
        if metric == "on_time_ratio":
            ax.set_ylim(0, 1.05)
        ax.legend(fontsize=9)

    fig.suptitle("Model Adaptive vs Static Compression — Overview", y=1.01,
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Plot comparison results from run_comparison.py"
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help=f"Path to comparison CSV (default: {DEFAULT_CSV})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_PLOTS,
                        help=f"Output directory for plots (default: {DEFAULT_PLOTS})")
    args = parser.parse_args()

    csv_path: Path = args.csv
    out_dir: Path  = args.out_dir

    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}")
        print("  Run run_comparison.py first to generate results.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {csv_path} ...")
    model_df, static_df, levels = load(csv_path)
    has_model = len(model_df) > 0
    print(f"  Static levels : {len(levels)}  ({levels[0]}–{levels[-1]})")
    print(f"  Model rows    : {len(model_df)}")
    print(f"  Users         : {sorted(static_df['user'].unique())}")
    print(f"\nGenerating plots → {out_dir}/")

    # 1. Effective error vs CL
    if has_model:
        fig_error_vs_cl(model_df, static_df, out_dir / "effective_error_vs_cl.png")
    else:
        print("  [SKIP] effective_error_vs_cl.png — no model rows")

    # 2. On-time ratio vs CL
    if has_model:
        fig_ontime_vs_cl(model_df, static_df, out_dir / "ontime_ratio_vs_cl.png")

    # 3. Delay vs CL
    if has_model:
        fig_delay_vs_cl(model_df, static_df, out_dir / "delay_vs_cl.png")

    # 4. Per-user error
    if has_model:
        fig_per_user_error(model_df, static_df, out_dir / "per_user_error.png")

    # 5. Per-video error
    if has_model and "video" in model_df.columns:
        fig_per_video_error(model_df, static_df, out_dir / "per_video_error.png")

    # 6. Overview (all metrics, bar chart)
    if has_model:
        fig_overview(model_df, static_df, levels, out_dir / "overview.png")

    print(f"\nDone. {len(list(out_dir.glob('*.png')))} PNG(s) in {out_dir}/")


if __name__ == "__main__":
    main()
