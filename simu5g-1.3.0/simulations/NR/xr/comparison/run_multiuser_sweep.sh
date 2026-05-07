#!/usr/bin/env bash
#
# Run run_comparison_parallel.py for multiple user counts and save each
# result as comparison_users{N}.csv inside comparison_results_{mode}/.
#
# Usage:
#   bash run_multiuser_sweep.sh              # defaults: pca, users 2-10
#   bash run_multiuser_sweep.sh --mode ae
#   bash run_multiuser_sweep.sh --mode pca --min-users 3 --max-users 8
#   bash run_multiuser_sweep.sh --mode pca --users "10"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Defaults ──────────────────────────────────────────────────────────────────
MODE="pca"
MIN_USERS=2
MAX_USERS=10
CUSTOM_USERS=""
SIM_TIME=35
SEED=42
MAX_WORKERS=31
EXTRA_ARGS=""

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)       MODE="$2";       shift 2 ;;
        --min-users)  MIN_USERS="$2";  shift 2 ;;
        --max-users)  MAX_USERS="$2";  shift 2 ;;
        --users)      CUSTOM_USERS="$2"; shift 2 ;;
        --sim-time)   SIM_TIME="$2";   shift 2 ;;
        --seed)       SEED="$2";       shift 2 ;;
        --max-workers) MAX_WORKERS="$2"; shift 2 ;;
        *)            EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
    esac
done

RESULTS_DIR="$SCRIPT_DIR/comparison_results_${MODE}"
mkdir -p "$RESULTS_DIR"

# Build list of user counts
if [[ -n "$CUSTOM_USERS" ]]; then
    USER_COUNTS=($CUSTOM_USERS)
else
    USER_COUNTS=($(seq "$MIN_USERS" "$MAX_USERS"))
fi

echo "================================================================="
echo "  Multi-User Sweep  (mode=${MODE})"
echo "================================================================="
echo "  User counts:  ${USER_COUNTS[*]}"
echo "  Sim time:     ${SIM_TIME}s"
echo "  Seed:         ${SEED}"
echo "  Results dir:  ${RESULTS_DIR}"
echo "================================================================="
echo ""

TOTAL=${#USER_COUNTS[@]}
IDX=0

for N in "${USER_COUNTS[@]}"; do
    IDX=$((IDX + 1))
    OUT_CSV="$RESULTS_DIR/comparison_users${N}.csv"

    echo "────────────────────────────────────────────────────────────"
    echo "  [$IDX/$TOTAL]  Running with --num-users $N ..."
    echo "────────────────────────────────────────────────────────────"

    python3 run_comparison_parallel.py \
        --mode "$MODE" \
        --num-users "$N" \
        --sim-time "$SIM_TIME" \
        --seed "$SEED" \
        --max-workers "$MAX_WORKERS" \
        $EXTRA_ARGS

    # Rename the generated comparison.csv → comparison_users{N}.csv
    SRC="$RESULTS_DIR/comparison.csv"
    if [[ -f "$SRC" ]]; then
        cp "$SRC" "$OUT_CSV"
        echo "  ✓ Saved: $OUT_CSV"
    else
        echo "  ✗ WARNING: $SRC not found after run with $N users"
    fi
    echo ""
done

echo "================================================================="
echo "  Sweep complete.  CSV files in $RESULTS_DIR:"
ls -1 "$RESULTS_DIR"/comparison_users*.csv 2>/dev/null || echo "  (none)"
echo "================================================================="
