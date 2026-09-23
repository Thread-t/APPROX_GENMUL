# FV-LIDAC exhaustive error-combo generation + equivalence verification.
#
# Build:
#   docker build -t fvlidac-verify .
#
# Run (quick smoke test, 4x4 multiplier, 500 random mask combos):
#   docker run --rm -v "$PWD/results:/results" fvlidac-verify \
#       --in1 4 --in2 4 --masks sample --sample-size 500 --outdir /results
#
# Run (full 65536-combo sweep, all cores by default, resumable if interrupted):
#   docker run --rm -v "$PWD/results:/results" fvlidac-verify \
#       --in1 4 --in2 4 --masks all --resume --outdir /results
#
# See `docker run --rm fvlidac-verify --help` for all options.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        yosys \
        iverilog \
        python3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Build genmul from the user's tool repo ---------------------------------
# Pass --build-arg GENMUL_REPO=<url> / GENMUL_REF=<branch, tag, or commit SHA>
# to point at a fork or pin an exact revision; defaults to main @ HEAD.
ARG GENMUL_REPO=https://github.com/Thread-t/APPROX_GENMUL.git
ARG GENMUL_REF=main

WORKDIR /opt
RUN git clone --depth 1 --branch "${GENMUL_REF}" "${GENMUL_REPO}" APPROX_GENMUL 2>/dev/null || \
    (git clone "${GENMUL_REPO}" APPROX_GENMUL && cd APPROX_GENMUL && git checkout "${GENMUL_REF}")

WORKDIR /opt/APPROX_GENMUL/build
RUN cmake -DCMAKE_BUILD_TYPE=Release .. \
    && make -j"$(nproc)" install

# Sanity-check the binary actually runs before baking it into the image.
# (genmul writes its .v output relative to the CWD it's invoked from, so cd
# into bin/ first -- an absolute path to genmul does not imply that.)
RUN cd /opt/APPROX_GENMUL/build/bin \
    && ./genmul 1 3 1 4 4 \
    && rm -f ./*.v

# --- Sweep tooling ------------------------------------------------------------
COPY sweep.py /opt/fvlidac/sweep.py
COPY equiv_check.ys.tpl /opt/fvlidac/equiv_check.ys.tpl
COPY verify_signed.py /opt/fvlidac/verify_signed.py
RUN chmod +x /opt/fvlidac/sweep.py /opt/fvlidac/verify_signed.py

WORKDIR /work
VOLUME ["/results"]

# Default entrypoint runs the exhaustive combo sweep (sweep.py). To run the
# signed-multiplier verifier (verify_signed.py) instead:
#   docker run --rm --entrypoint python3 fvlidac-verify \
#       /opt/fvlidac/verify_signed.py --genmul /opt/APPROX_GENMUL/build/bin/genmul \
#       --in1 8 --in2 8
ENTRYPOINT ["python3", "/opt/fvlidac/sweep.py", "--genmul", "/opt/APPROX_GENMUL/build/bin/genmul"]
CMD ["--help"]
