#!/usr/bin/env bash

# Define the output directory on the host machine
HOST_RESULTS_DIR="$PWD/results16_wallace_sample"

# Create the output directory first to ensure your user owns it (not Docker's root user)
mkdir -p "$HOST_RESULTS_DIR"

echo "=================================================="
echo " Testing Approximate Wallace Tree (Sample of 5)   "
echo " Signed Mode, 16x16, Column: 17                   "
echo "=================================================="

# Run the python sweep script via Docker
docker run --rm --entrypoint python3 \
    -v "$HOST_RESULTS_DIR:/results" \
    fvlidac-verify /opt/fvlidac/sweep.py \
    --genmul /opt/APPROX_GENMUL/build/bin/genmul \
    --arch wallace \
    --in1 16 --in2 16 --signed \
    --masks sample --sample-size 5 \
    --column 17 \
    --jobs 1 --verbose \
    --outdir /results

echo "=================================================="
echo " Test completed! Results saved to:"
echo " $HOST_RESULTS_DIR/results.csv"
echo "=================================================="