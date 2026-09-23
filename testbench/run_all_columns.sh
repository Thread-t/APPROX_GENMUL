#!/usr/bin/env bash

IN1=16
IN2=16
MAX_COL=$((IN1 + IN2 - 2))  # Automatically calculates 30 for 16x16
HOST_RESULTS_DIR="$PWD/results16"

mkdir -p "$HOST_RESULTS_DIR"

echo "=================================================="
echo " Starting Full Sweep Across Columns 0 to $MAX_COL"
echo "=================================================="

for col in $(seq 0 $MAX_COL); do
    echo "--------------------------------------------------"
    echo " RUNNING SWEEP FOR COLUMN: $col / $MAX_COL"
    echo "--------------------------------------------------"

    docker run --rm --entrypoint python3 \
        -v "$HOST_RESULTS_DIR:/results" \
        fvlidac-verify /opt/fvlidac/sweep.py \
        --genmul /opt/APPROX_GENMUL/build/bin/genmul \
        --in1 $IN1 --in2 $IN2 --signed \
        --masks all \
        --column $col \
        --exclude "23:105" \
        --jobs 8 \
        --timeout 1800 \
        --resume \
        --outdir "/results/col_${col}"

    echo "Completed Column $col. Saved to: $HOST_RESULTS_DIR/col_${col}/results.csv"
done

echo "=================================================="
echo " All columns (0 to $MAX_COL) completed!"
echo "=================================================="