#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d build ]]; then
  cmake -S . -B build >/dev/null
fi

if [[ ! -x build/bin/genmul && ! -x build/src/genmul ]]; then
  cmake -S . -B build >/dev/null
fi

cmake --build build -j"$(nproc 2>/dev/null || echo 4)" >/dev/null

exec python3 src/genmul_gui.py "$@"
