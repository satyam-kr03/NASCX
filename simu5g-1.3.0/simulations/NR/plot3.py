import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.ticker as mticker

plt.rcParams.update({
    "figure.dpi": 300,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#E4E4E4",
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "text.color": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
})

def discover_csvs(results_dir: Path) -> dict[int, Path]:
    mapping: dict[int, Path] = {}
    for p in sorted(results_dir.glob("comparison_users*.csv")):
        stem = p.stem
        try:
            n = int(stem.replace("comparison_users", ""))
            mapping[n] = p
        except ValueError:
            continue
    return dict(sorted(mapping.items()))

def get_best_cl_by_users(csv_map: dict[int, Path]) -> pd.DataFrame:
    records = []
    for n_users, path in csv_map.items():
        df = pd.read_csv(path)
        static = df[df["strategy"] == "static"].copy()
        if static.empty:
            continue
        static["comp_level"] = static["comp_level"].astype(int)
        
        # Calculate mean effective error by CL
        cl_means = static.groupby("comp_level")["mean_effective_error"].mean()
        best_cl = int(cl_means.idxmin())
        records.append({"num_users": n_users, "best_cl": best_cl})
        
    return pd.DataFrame(records).sort_values("num_users")

def plot_best_cl_on_ax(ax, df: pd.DataFrame, title: str, color: str):
    if df.empty:
        ax.text(0.5, 0.5, "Data not found", ha='center')
        return

    users = df["num_users"].values
    best_cl = df["best_cl"].values

    # Bar chart is great for discrete quantities like CL
    ax.bar(users, best_cl, width=0.6, color=color, alpha=0.85, edgecolor='black', linewidth=0.5)
    
    ax.set_xticks(users)
    ax.set_xlabel("Number of Users")
    ax.set_ylabel("Best Compression Level (K)")
    ax.set_title(title)
    
    # CL values are multiples of 5, up to 80
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
    ax.set_ylim(0, 85)

def main():
    base_dir = Path(__file__).parent.resolve()
    
    results_new = base_dir / "xr_new/comparison/comparison_results_pca"
    results_small = base_dir / "xr_small/comparison/comparison_results_pca"
    results_large = base_dir / "xr_large/comparison/comparison_results_pca"
    
    csv_map_new = discover_csvs(results_new)
    csv_map_small = discover_csvs(results_small)
    csv_map_large = discover_csvs(results_large)
    
    df_new = get_best_cl_by_users(csv_map_new)
    df_small = get_best_cl_by_users(csv_map_small)
    df_large = get_best_cl_by_users(csv_map_large)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    if not df_small.empty and not df_new.empty:
        users = df_small["num_users"].values
        # Assume both dataframes have the same users
        best_cl_small = df_small["best_cl"].values
        best_cl_new = df_new["best_cl"].values
        best_cl_large = df_large["best_cl"].values 
        
        bar_width = 0.25
        offset = 0.28
        index = np.arange(len(users))
        
        ax.bar(index - offset, best_cl_small, bar_width, label="Delay Deadline = 3 ms", color="#D55E00", alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.bar(index, best_cl_new, bar_width, label="Delay Deadline = 5 ms", color="#2B7BB9", alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.bar(index + offset, best_cl_large, bar_width, label="Delay Deadline = 10 ms", color="#009E73", alpha=0.85, edgecolor='black', linewidth=0.5)
        
        
        ax.set_xticks(index)
        ax.set_xticklabels(users)
        ax.set_xlabel("Number of Users")
        ax.set_ylabel("Best Compression Level (K)")
        ax.set_title("Best Compression Level vs Number of Users")
        ax.legend()
        
        ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
        ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
        ax.set_ylim(0, 85)
    else:
        ax.text(0.5, 0.5, "Data not found", ha='center')
    
    fig.tight_layout()
    out_path = base_dir / "best_cl_vs_users_combined.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Saved figure to {out_path}")

if __name__ == "__main__":
    main()