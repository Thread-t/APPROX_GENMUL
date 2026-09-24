#!/usr/bin/env bash

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <START_COL> <END_COL>"
    echo "Example: $0 0 5"
    exit 1
fi

START_COL=$1
END_COL=$2

IN1=16
IN2=16
HOST_RESULTS_DIR="$PWD/results16_array"

mkdir -p "$HOST_RESULTS_DIR"

echo "=================================================="
echo " Starting Array Multiplier Sweep: Columns $START_COL to $END_COL"
echo "=================================================="

for col in $(seq $START_COL $END_COL); do
    echo "--------------------------------------------------"
    echo " RUNNING SWEEP FOR ARRAY MULTIPLIER COLUMN: $col"
    echo "--------------------------------------------------"

    docker run --rm --entrypoint python3 \
        -v "$HOST_RESULTS_DIR:/results" \
        fvlidac-verify /opt/fvlidac/sweep.py \
        --genmul /opt/APPROX_GENMUL/build/bin/genmul \
        --arch array \
        --in1 $IN1 --in2 $IN2 --signed \
        --masks all \
        --column $col \
        --exclude "23:105" \
        --jobs 4 \
        --timeout 1800 \
        --resume \
        --outdir "/results/col_${col}"

    echo "Completed Array Column $col. Saved to: $HOST_RESULTS_DIR/col_${col}/results.csv"
done