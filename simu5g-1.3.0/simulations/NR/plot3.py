import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.ticker as mticker

plt.rcParams.update({
    "figure.dpi": 600,             
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#E4E4E4",
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.frameon": False,       
    "legend.fontsize": 8,          # Bumped back up slightly since text is shorter
    "text.color": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
})

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

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
        
        cl_means = static.groupby("comp_level")["mean_effective_error"].mean()
        best_cl = int(cl_means.idxmin())
        records.append({"num_users": n_users, "best_cl": best_cl})
        
    return pd.DataFrame(records).sort_values("num_users")

def main():
    base_dir = Path(__file__).parent.resolve()
    
    results = {
        "strict_60fps": base_dir / "xr_strict_60fps/comparison/comparison_results_pca",
        "strict_90fps": base_dir / "xr_strict_90fps/comparison/comparison_results_pca",
        "relaxed_60fps": base_dir / "xr_relaxed_60fps/comparison/comparison_results_pca",
        "relaxed_90fps": base_dir / "xr_relaxed_90fps/comparison/comparison_results_pca",
    }

    dfs = {}
    for key, path in results.items():
        csv_map = discover_csvs(path)
        dfs[key] = get_best_cl_by_users(csv_map)

    not_empty = [name for name, df in dfs.items() if not df.empty]
    if not not_empty:
        print("No data found in any result directories")
        return

    merged = None
    for key, df in dfs.items():
        if df.empty:
            continue
        df = df.rename(columns={"best_cl": f"best_cl_{key}"})
        if merged is None:
            merged = df
        else:
            merged = pd.merge(merged, df, on="num_users", how="outer")

    if merged is None or merged.empty:
        print("No overlapping user counts found across datasets")
        return

    merged = merged.sort_values("num_users").reset_index(drop=True)
    users = merged["num_users"].values

    # Clean, objective, concise labels
    categories = [
        ("relaxed_60fps", "dₘₐₓ=5 ms, 60 fps", "#FD8D3C"),
        ("relaxed_90fps", "dₘₐₓ=5 ms, 90 fps", "#B10026"),
        ("strict_60fps",  "dₘₐₓ=2.5 ms, 60 fps",  "#74A9CF"),
        ("strict_90fps",  "dₘₐₓ=2.5 ms, 90 fps",  "#045A8D"),
    ]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    bar_width = 0.18  
    index = np.arange(len(users))
    
    offsets = [-1.5 * bar_width, -0.5 * bar_width, 0.5 * bar_width, 1.5 * bar_width]

    for offset, (key, label, color) in zip(offsets, categories):
        col = f"best_cl_{key}"
        if col not in merged.columns:
            continue
        y = merged[col].values
        ax.bar(
            index + offset, y, bar_width, 
            label=label, color=color, 
            alpha=0.9, edgecolor='black', linewidth=0.5
        )

    ax.set_xticks(index)
    ax.set_xticklabels(users)
    ax.set_xlabel("Number of Users", labelpad=2)
    ax.set_ylabel("Optimal Compression Level", labelpad=2) 
    
    # Restored natural spacing since labels are shorter
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=2,
        columnspacing=0.8,
        handletextpad=0.4
    )

    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
    ax.set_ylim(0, 85)

    fig.tight_layout()
    out_path = base_dir / "best_cl_vs_users_combined.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=600)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Saved figure to {out_path}")

if __name__ == "__main__":
    main()