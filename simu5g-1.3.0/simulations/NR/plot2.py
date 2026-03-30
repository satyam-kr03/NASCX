import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

PALETTE = {
    "min_cl":  "#4DAF4A",   # green
    "optimal_cl":  "#FF7F00",   # orange
    "max_cl":  "#984EA3",   # purple
    "model":   "#E84040",   # vivid red
    "grid":    "#E4E4E4",
    "text":    "#2B2B2B",
}

BAR_COLORS = [
    PALETTE["min_cl"],
    PALETTE["optimal_cl"],
    PALETTE["max_cl"],
    PALETTE["model"],
]

BAR_LABELS = [
    "High Compression (K = 5)",
    "Optimal Static Compression ($K_{\mathrm{opt}}$)",
    "Low Compression (K = 80)",
    "Adaptive Compression (Dynamic K)",
]

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

def load_all(csv_map: dict[int, Path]) -> pd.DataFrame:
    frames = []
    for n_users, path in csv_map.items():
        df = pd.read_csv(path)
        df["num_users"] = n_users
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames, ignore_index=True)
    if "mean_effective_error" in df_all.columns:
        df_all["mean_effective_error"] = np.sqrt(df_all["mean_effective_error"] / (255.0 * 255.0))
    return df_all

def aggregate_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    records = []
    for n_users, grp in df.groupby("num_users"):
        static = grp[grp["strategy"] == "static"].copy()
        model  = grp[grp["strategy"] == "model"]
        if static.empty:
            continue
        static["comp_level"] = static["comp_level"].astype(int)
        levels = sorted(static["comp_level"].unique())
        min_cl, max_cl = levels[0], levels[-1]

        cl_means = static.groupby("comp_level")[metric].mean()
        if metric == "on_time_ratio":
            optimal_cl = int(cl_means.idxmax())
        else:
            optimal_cl = int(cl_means.idxmin())

        model_val = float(model[metric].mean()) if not model.empty else float("nan")

        records.append({
            "num_users":      n_users,
            "min_cl":         min_cl,
            "max_cl":         max_cl,
            "optimal_cl":     optimal_cl,
            "min_cl_val":     float(cl_means.get(min_cl, float("nan"))),
            "optimal_cl_val": float(cl_means.get(optimal_cl, float("nan"))),
            "max_cl_val":     float(cl_means.get(max_cl, float("nan"))),
            "best_static":    float(cl_means.get(optimal_cl, float("nan"))),
            "model_val":      model_val,
        })
    if len(records) == 0:
        return pd.DataFrame()
    return pd.DataFrame(records).set_index("num_users")

def _build_values(agg: pd.DataFrame) -> np.ndarray:
    return np.column_stack([
        agg["min_cl_val"].values,
        agg["optimal_cl_val"].values,
        agg["max_cl_val"].values,
        agg["model_val"].values,
    ])

def plot_grouped_bar_on_ax(ax, df: pd.DataFrame, title: str, add_legend: bool = False):
    if df.empty:
        ax.text(0.5, 0.5, "Data not found", ha='center')
        return

    agg = aggregate_metric(df, "mean_effective_error")
    if agg.empty:
        ax.text(0.5, 0.5, "Aggregation empty", ha='center')
        return

    user_counts = list(agg.index)
    values = _build_values(agg)

    n_groups = len(user_counts)
    n_bars = values.shape[1]
    width = 0.25
    x = np.arange(n_groups) * 1.25

    HATCHES = ['//', '\\\\', 'xx', '']

    for j in range(n_bars):
        offset = (j - n_bars / 2 + 0.5) * width
        ax.bar(
            x + offset, values[:, j], width,
            color=BAR_COLORS[j], label=BAR_LABELS[j] if add_legend else None, alpha=0.88,
            edgecolor="white", linewidth=0.5, hatch=HATCHES[j % len(HATCHES)],
        )

    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in user_counts])
    ax.set_xlabel("Number of Users")
    ax.set_ylabel(r"Mean Error ($\bar{\varepsilon}$)")
    ax.set_title(title)
    
    bottom, top = ax.get_ylim()
    ax.set_ylim(bottom, top + (top - bottom) * 0.20)
    
    if add_legend:
        ax.legend(loc="upper left", ncol=2, fontsize=8)


def main():
    base_dir = Path(__file__).parent.resolve()
    
    results_new = base_dir / "xr_strict_90fps/comparison/comparison_results_pca"
    results_small = base_dir / "xr_relaxed_90fps/comparison/comparison_results_pca"
    
    csv_map_new = discover_csvs(results_new)
    csv_map_small = discover_csvs(results_small)
    
    df_new = load_all(csv_map_new)
    df_small = load_all(csv_map_small)
    
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.2), sharey=True)
    
    plot_grouped_bar_on_ax(axes[0], df_new, "Delay Deadline = 5 ms", add_legend=True)
    plot_grouped_bar_on_ax(axes[1], df_small, "Delay Deadline = 10 ms", add_legend=False)

    fig.tight_layout()
    fig.subplots_adjust(wspace=0.1)
    
    out_path = base_dir / "effective_error_by_users_combined.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"Saved figure to {out_path}")

if __name__ == "__main__":
    main()