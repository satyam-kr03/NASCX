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

def load(csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    df = pd.read_csv(csv_path)
    model_df  = df[df["strategy"] == "model"].copy()
    static_df = df[df["strategy"] == "static"].copy()
    static_df["comp_level"] = static_df["comp_level"].astype(int)
    levels = sorted(static_df["comp_level"].unique())
    return model_df, static_df, levels

def static_agg(static_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    return (
        static_df.groupby("comp_level")[metric]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
        .sort_values("comp_level")
    )

def model_stats(model_df: pd.DataFrame, metric: str) -> tuple[float, float, float]:
    vals = model_df[metric].dropna()
    return float(vals.mean()), float(vals.std()), float(vals.sem())

def plot_single(ax, model_df, static_df, label_suffix, color_static, color_model, marker="o"):
    agg = static_agg(static_df, "mean_effective_error")
    agg["mean"] /= (255 * 255)
    agg["std"] /= (255 * 255)
    agg["mean"] = np.sqrt(agg["mean"])
    agg["std"] = np.sqrt(agg["std"])
    m_mean, _, _ = model_stats(model_df, "mean_effective_error")
    m_mean /= (255 * 255)
    m_mean = np.sqrt(m_mean)
    
    ax.plot(
        agg["comp_level"], agg["mean"],
        color=color_static, linewidth=2, marker=marker, markersize=5,
        label=f"Static ({label_suffix})",
    )
    
    ax.axhline(m_mean, color=color_model, linewidth=2.0,
               linestyle="--", label=f"Adaptive ({label_suffix})\n(μ={m_mean:.4f})")

def main():
    base_dir = Path(__file__).parent.resolve()
    
    csv_new = base_dir / "xr_new/comparison/comparison_results_pca/comparison_users5.csv"
    csv_small = base_dir / "xr_small/comparison/comparison_results_pca/comparison_users5.csv"
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    if csv_new.exists():
        model_df_new, static_df_new, _ = load(csv_new)
        plot_single(ax, model_df_new, static_df_new, "5 ms", PALETTE["static"], PALETTE["model"], marker="o")
        
    if csv_small.exists():
        model_df_small, static_df_small, _ = load(csv_small)
        # Using a distinct color palette for the 10ms deadline curves so they are distinguishable
        plot_single(ax, model_df_small, static_df_small, "3 ms", "#009E73", "#D55E00", marker="s")

    ax.set_xlabel("Components (K)")
    ax.set_ylabel("Mean Effective Error (μ)")
    ax.set_title("Effective Error vs Components (5 ms vs 3 ms Deadline)")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    
    bottom, top = ax.get_ylim()
    ax.set_ylim(bottom, top + (top - bottom) * 0.45)
    
    # We use 2 columns in legend to keep it from taking too much vertical space
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    fig.tight_layout()
    out_path = base_dir / "error_vs_cl_combined.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Saved figure to {out_path}")

if __name__ == "__main__":
    main()
