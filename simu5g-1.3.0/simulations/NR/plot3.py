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
    ax.set_ylabel("Optimal Compression Level (K)")
    ax.set_title(title)
    
    # CL values are multiples of 5, up to 80
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
    ax.set_ylim(0, 85)

def main():
    base_dir = Path(__file__).parent.resolve()
    
    results_60fps = base_dir / "xr_strict_60fps/comparison/comparison_results_pca"
    results_90fps = base_dir / "xr_strict_90fps/comparison/comparison_results_pca"

    
    csv_map_60fps = discover_csvs(results_60fps)
    csv_map_90fps = discover_csvs(results_90fps)
    
    df_60fps = get_best_cl_by_users(csv_map_60fps)
    df_90fps = get_best_cl_by_users(csv_map_90fps)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    if not df_60fps.empty and not df_90fps.empty:
        # enforce alignment to avoid accidental label swapping
        merged = pd.merge(df_60fps, df_90fps, on="num_users", how="inner", suffixes=("_60fps", "_90fps"))
        if merged.empty:
            ax.text(0.5, 0.5, "No overlapping user counts found", ha='center')
            return

        users = merged["num_users"].values
        best_cl_60fps = merged["best_cl_60fps"].values
        best_cl_90fps = merged["best_cl_90fps"].values

        bar_width = 0.35
        index = np.arange(len(users))

        ax.bar(index - bar_width/2, best_cl_60fps, bar_width, label="Moderate Load (60fps)", color="#D55E00", alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.bar(index + bar_width/2, best_cl_90fps, bar_width, label="High Load (90fps)", color="#2B7BB9", alpha=0.85, edgecolor='black', linewidth=0.5)

        ax.set_xticks(index)
        ax.set_xticklabels(users)
        ax.set_xlabel("Number of Users")
        ax.set_ylabel("Optimal Compression Level (K)")
        ax.set_title("Optimal Compression Level vs Number of Users")
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