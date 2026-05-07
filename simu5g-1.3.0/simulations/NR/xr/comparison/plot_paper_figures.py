#!/usr/bin/env python3
"""
Paper Figure Generator for NASCX XR Compression Comparison.

Produces the three core figures used in the paper:

  Figure 1: ε̄ vs K  — Mean effective error as a function of static
            compression level K, for a fixed number of users N.

  Figure 2: K_opt vs N — Optimal static compression level versus
            number of users N.

  Figure 3: ε̄ vs N   — Mean effective error versus N for different
            delay bounds (requires sweeps at multiple deadlines).

Usage:
    python plot_paper_figures.py --figure 1 --num-users 5
    python plot_paper_figures.py --figure 2
    python plot_paper_figures.py --figure 3
    python plot_paper_figures.py --all
    python plot_paper_figures.py --all --out-dir my_plots
"""

import argparse
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd


# ── Shared Style ─────────────────────────────────────────────────────────────

PALETTE = {
    "model":  "#E84040",   # vivid red for model/adaptive
    "static": "#2B7BB9",   # steel blue for static
    "band":   "#F5AAAA",   # light red fill for model CI band
    "grid":   "#E4E4E4",
    "accent": ["#4DAF4A", "#FF7F00", "#984EA3", "#A65628"],
}

plt.rcParams.update({
    "figure.dpi": 300,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": PALETTE["grid"],
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "font.family": "serif",
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


# ── Data loading helpers ─────────────────────────────────────────────────────

def load_comparison_csv(csv_path: Path) -> tuple:
    """Load a comparison CSV and split into model/static DataFrames."""
    df = pd.read_csv(csv_path)
    model_df = df[df["strategy"] == "model"].copy()
    static_df = df[df["strategy"] == "static"].copy()
    static_df["comp_level"] = static_df["comp_level"].astype(int)
    levels = sorted(static_df["comp_level"].unique())
    return model_df, static_df, levels


def discover_user_csvs(results_dir: Path) -> dict:
    """Find comparison_users{N}.csv files → {N: Path}."""
    mapping = {}
    for p in sorted(results_dir.glob("comparison_users*.csv")):
        try:
            n = int(p.stem.replace("comparison_users", ""))
            mapping[n] = p
        except ValueError:
            continue
    return dict(sorted(mapping.items()))


def static_agg(static_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Aggregate a metric over users, grouped by comp_level."""
    return (
        static_df.groupby("comp_level")[metric]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
        .sort_values("comp_level")
    )


def normalize_error(values):
    """Convert MSE to normalized RMSE: sqrt(mse / 255^2)."""
    return np.sqrt(np.array(values, dtype=float) / (255.0 * 255.0))


# ── Figure 1: ε̄ vs K ────────────────────────────────────────────────────────

def fig_error_vs_cl(
    csv_path: Path, out_dir: Path, num_users: Optional[int] = None,
) -> None:
    """Mean effective error vs compression level K for a given N.

    If num_users is provided, loads comparison_users{N}.csv.
    Otherwise loads the default comparison.csv.
    """
    if num_users is not None:
        csv_path = csv_path.parent / f"comparison_users{num_users}.csv"

    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found")
        return

    model_df, static_df, levels = load_comparison_csv(csv_path)
    agg = static_agg(static_df, "mean_effective_error")

    # Normalize to RMSE scale
    agg_mean = normalize_error(agg["mean"].values)
    model_mean = normalize_error([model_df["mean_effective_error"].mean()])[0] if len(model_df) > 0 else None

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(
        agg["comp_level"], agg_mean,
        color=PALETTE["static"], linewidth=2, marker="o", markersize=5,
        label="Static (mean across users)",
    )

    if model_mean is not None:
        ax.axhline(
            model_mean, color=PALETTE["model"], linewidth=2.0,
            linestyle="--",
            label=f"Network-Aware\nDynamic Selection (μ={model_mean:.4f})",
        )

    n_label = f" (N={num_users})" if num_users else ""
    ax.set_xlabel("Components (K)")
    ax.set_ylabel("Mean Effective Error (ε̄)")
    ax.set_title(f"ε̄ vs K{n_label}")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    bottom, top = ax.get_ylim()
    ax.set_ylim(bottom, top + (top - bottom) * 0.35)
    ax.legend(loc="upper center", fontsize=7)
    fig.tight_layout()

    suffix = f"_n{num_users}" if num_users else ""
    out = out_dir / f"fig1_error_vs_cl{suffix}"
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.stem}.pdf/.png")


# ── Figure 2: K_opt vs N ────────────────────────────────────────────────────

def fig_kopt_vs_n(results_dir: Path, out_dir: Path) -> None:
    """Optimal static compression level K_opt vs number of users N."""
    csv_map = discover_user_csvs(results_dir)
    if not csv_map:
        print("  [SKIP] No comparison_users*.csv files found")
        return

    user_counts = []
    k_opts = []

    for n_users, csv_path in csv_map.items():
        _, static_df, _ = load_comparison_csv(csv_path)
        agg = static_agg(static_df, "mean_effective_error")
        best_idx = agg["mean"].idxmin()
        k_opt = int(agg.loc[best_idx, "comp_level"])
        user_counts.append(n_users)
        k_opts.append(k_opt)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(
        user_counts, k_opts,
        color=PALETTE["static"], linewidth=2, marker="s", markersize=6,
        markerfacecolor="white", markeredgewidth=2,
    )

    ax.set_xlabel("Number of Users (N)")
    ax.set_ylabel("Optimal Static CL (K_opt)")
    ax.set_title("K_opt vs N")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.set_xlim(min(user_counts) - 0.5, max(user_counts) + 0.5)

    fig.tight_layout()
    out = out_dir / "fig2_kopt_vs_n"
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.stem}.pdf/.png")


# ── Figure 3: ε̄ vs N for multiple delay bounds ──────────────────────────────

def fig_error_vs_n_multibound(results_dir: Path, out_dir: Path) -> None:
    """Mean effective error vs N, one curve per delay bound.

    Expects directories named comparison_results_pca_dXms/ where X is the
    deadline in ms (e.g., comparison_results_pca_d2ms, _d5ms, _d10ms).
    Falls back to a single-deadline plot if only one directory exists.
    """
    # Discover deadline-specific result directories
    parent = results_dir.parent
    deadline_dirs = sorted(parent.glob("comparison_results_pca*"))

    deadline_data = {}
    for d in deadline_dirs:
        # Extract deadline from directory name
        name = d.name
        if "comparison_results_pca_d" in name:
            try:
                deadline = name.split("_d")[1].replace("ms", "")
                deadline = float(deadline)
            except (IndexError, ValueError):
                continue
        elif name == "comparison_results_pca":
            deadline = 5.0  # Default deadline
        else:
            continue

        csv_map = discover_user_csvs(d)
        if csv_map:
            deadline_data[deadline] = csv_map

    if not deadline_data:
        # Single-deadline fallback
        csv_map = discover_user_csvs(results_dir)
        if csv_map:
            deadline_data[5.0] = csv_map
        else:
            print("  [SKIP] No comparison data found for multi-deadline plot")
            return

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    colors = [PALETTE["static"]] + PALETTE["accent"]

    for idx, (deadline, csv_map) in enumerate(sorted(deadline_data.items())):
        user_counts = []
        model_errors = []

        for n_users, csv_path in csv_map.items():
            model_df, _, _ = load_comparison_csv(csv_path)
            if len(model_df) > 0:
                err = normalize_error([model_df["mean_effective_error"].mean()])[0]
                user_counts.append(n_users)
                model_errors.append(err)

        if user_counts:
            color = colors[idx % len(colors)]
            ax.plot(
                user_counts, model_errors,
                linewidth=2, marker="o", markersize=5,
                color=color,
                label=f"Deadline = {deadline:.1f} ms",
            )

    ax.set_xlabel("Number of Users (N)")
    ax.set_ylabel("Mean Effective Error (ε̄)")
    ax.set_title("ε̄ vs N (Model-Adaptive)")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    bottom, top = ax.get_ylim()
    ax.set_ylim(bottom, top + (top - bottom) * 0.35)
    ax.legend(loc="upper left", fontsize=7)
    fig.tight_layout()

    out = out_dir / "fig3_error_vs_n_multibound"
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.stem}.pdf/.png")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate paper figures from comparison results"
    )
    parser.add_argument(
        "--figure", type=int, choices=[1, 2, 3],
        help="Generate a specific figure (1, 2, or 3)",
    )
    parser.add_argument("--all", action="store_true", help="Generate all 3 figures")
    parser.add_argument(
        "--num-users", type=int, default=5,
        help="Number of users for Figure 1 (default: 5)",
    )
    parser.add_argument(
        "--results-dir", type=Path,
        default=SCRIPT_DIR / "comparison_results_pca",
        help="Directory containing comparison CSV files",
    )
    parser.add_argument(
        "--out-dir", type=Path,
        default=SCRIPT_DIR / "plots",
        help="Output directory for figures",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.results_dir / "comparison.csv"

    figures_to_gen = set()
    if args.all:
        figures_to_gen = {1, 2, 3}
    elif args.figure:
        figures_to_gen = {args.figure}
    else:
        print("Specify --figure N or --all. Use --help for details.")
        return

    print(f"Generating figures → {args.out_dir}/\n")

    if 1 in figures_to_gen:
        print("[Figure 1] ε̄ vs K")
        fig_error_vs_cl(csv_path, args.out_dir, num_users=args.num_users)

    if 2 in figures_to_gen:
        print("[Figure 2] K_opt vs N")
        fig_kopt_vs_n(args.results_dir, args.out_dir)

    if 3 in figures_to_gen:
        print("[Figure 3] ε̄ vs N (multi-deadline)")
        fig_error_vs_n_multibound(args.results_dir, args.out_dir)

    n_pdfs = len(list(args.out_dir.glob("*.pdf")))
    print(f"\nDone. {n_pdfs} PDF(s) in {args.out_dir}/")


if __name__ == "__main__":
    main()
