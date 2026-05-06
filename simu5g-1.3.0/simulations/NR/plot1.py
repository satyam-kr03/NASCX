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
    "figure.dpi": 600,         # Crisp lines for print
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": PALETTE["grid"],
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.frameon": False,   # Clean, borderless legend
    "legend.fontsize": 8,      # Slightly smaller for the 1-col width
    "text.color": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
})

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

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
        # Scaled down linewidth and marker size for 3.5in figure
        color=color_static, linewidth=1.5, marker=marker, markersize=4,
        label=f"Static ({label_suffix})",
    )
    
    ax.axhline(
        m_mean,
        color=color_model,
        linewidth=1.5,
        linestyle="--",
        label=f"Adaptive ({label_suffix})\n(mean error={m_mean:.4f})",
    )

def main():
    base_dir = Path(__file__).parent.resolve()
    
    # EXACT IEEE SINGLE COLUMN WIDTH (3.5 inches)
    fig, ax = plt.subplots(figsize=(3.5, 2.8)) 
    
    csv_new = base_dir / "xr_experimental_2.5ms/comparison/comparison_results_pca/comparison_users10.csv"
    csv_large = base_dir / "xr_experimental_5ms/comparison/comparison_results_pca/comparison_users10.csv"
    
    if csv_new.exists():
        model_df_new, static_df_new, _ = load(csv_new)
        plot_single(ax, model_df_new, static_df_new, "2.5 ms", PALETTE["static"], PALETTE["model"], marker="o")
        
    if csv_large.exists():
        model_df_large, static_df_large, _ = load(csv_large)
        plot_single(ax, model_df_large, static_df_large, "5 ms", "#009E73", "#D55E00", marker="s")

    ax.set_xlabel("Components", labelpad=2)
    ax.set_ylabel("Mean Error", labelpad=2)
    
    # NOTE: Titles inside figures are discouraged in IEEE. Use the LaTeX \caption instead.
    # ax.set_title("Error vs Components (5 ms vs 10 ms Deadline)")
    
    ax.xaxis.set_major_locator(mticker.MultipleLocator(10))
    
    # Clean top/bottom margins instead of wasting 45% vertical space
    ax.margins(y=0.1)
    
    # Place legend above the plot, squeezing columns slightly to fit the 3.5" width
    ax.legend(
        loc="lower center", 
        bbox_to_anchor=(0.5, 1.02), 
        ncol=2, 
        fontsize=8,
        columnspacing=0.8 
    )

    fig.tight_layout()
    
    out_path = base_dir / "error_vs_cl_combined.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=600)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Saved figure to {out_path}")

if __name__ == "__main__":
    main()