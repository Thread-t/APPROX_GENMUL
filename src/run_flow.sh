#!/usr/bin/env bash
set -uo pipefail

# Arguments passed from Python GUI:
#   $1 = genmul binary path
#   $2 = output directory
#   $3 = PPG
#   $4 = PPA
#   $5 = FSA
#   $6 = IN1
#   $7 = IN2
#   $8 = COL
#   $9 = COUT
#  $10 = SUM
#  $11 = METHOD
#  $12 = DEBUG

#Sayak: Read and identify the user inputs from the python gui inputs
GENMUL_BIN="${1:?usage: $0 <genmul_bin> <out_dir> <ppg> <ppa> <fsa> <in1> <in2> [col] [cout] [sum] [method] [debug>] }"
OUT_DIR="${2:?usage: $0 <genmul_bin> <out_dir> <ppg> <ppa> <fsa> <in1> <in2> [col] [cout] [sum] [method] [debug>] }"
PPG="${3:-1}"
PPA="${4:-1}"
FSA="${5:-1}"
IN1="${6:-8}"
IN2="${7:-8}"
COL="${8:-0}"
COUT="${9:-0}"
SUM="${10:-0}"
METHOD="${11:-0}"
DEBUG="${12:-0}"

#Sayak: check where is my love!! XD
if command -v realpath >/dev/null 2>&1; then
    GENMUL_BIN="$(realpath "$GENMUL_BIN")"
    OUT_DIR="$(realpath -m "$OUT_DIR")"
else
    GENMUL_BIN="$(cd "$(dirname "$GENMUL_BIN")" && pwd)/$(basename "$GENMUL_BIN")"
    OUT_DIR="$(mkdir -p "$OUT_DIR" && cd "$OUT_DIR" && pwd)"
fi

mkdir -p "$OUT_DIR"
cd "$OUT_DIR"

LOG_DIR="$OUT_DIR/equiv_check_logs"
mkdir -p "$LOG_DIR"

# Line-buffer yosys/abc's own stdout so it streams to the terminal as it is
# produced instead of arriving in one big chunk at the end (what was making
# this look "stuck" on anything but a trivial design).
STDBUF=()
if command -v stdbuf >/dev/null 2>&1; then
    STDBUF=(stdbuf -oL -eL)
fi

# Remove stale generated files before creating new ones.
rm -f "${IN1}_${IN2}"*"_GenMul.v"

# Sayak: Core step Map approximate PPA options to their exact counterparts.
GOLDEN_PPA="$PPA"
case "$PPA" in
    5) GOLDEN_PPA=3 ;; # Approx Dadda -> Exact Dadda
    6) GOLDEN_PPA=1 ;; # Approx Array -> Exact Array
    7) GOLDEN_PPA=2 ;; # Approx Wallace -> Exact Wallace
    *) GOLDEN_PPA="$PPA" ;;
esac

echo "=================================================="
echo " 1. Generating Approximate RTL Design"
echo "=================================================="
if [[ "$PPA" =~ ^[567]$ ]]; then
    "$GENMUL_BIN" "$PPG" "$PPA" "$FSA" "$IN1" "$IN2" "$COL" "$COUT" "$SUM" "$METHOD" "$DEBUG"
else
    "$GENMUL_BIN" "$PPG" "$PPA" "$FSA" "$IN1" "$IN2"
fi
if [[ $? -ne 0 ]]; then
    echo "ERROR: genmul failed while generating the approximate design."
    exit 1
fi
APPROX_V="$(ls -t "${IN1}_${IN2}"*"_GenMul.v" | head -n 1)"
if [[ -z "$APPROX_V" ]]; then
    echo "ERROR: Approximate RTL generation did not produce a file in $OUT_DIR"
    exit 1
fi
echo "Generated: $APPROX_V"

echo ""
echo "=================================================="
echo " 2. Deriving & Generating Golden (Exact) RTL Design"
echo "=================================================="
if [[ "$GOLDEN_PPA" =~ ^[567]$ ]]; then
    "$GENMUL_BIN" "$PPG" "$GOLDEN_PPA" "$FSA" "$IN1" "$IN2" 0 0 0 0 0
else
    "$GENMUL_BIN" "$PPG" "$GOLDEN_PPA" "$FSA" "$IN1" "$IN2"
fi
if [[ $? -ne 0 ]]; then
    echo "ERROR: genmul failed while generating the golden design."
    exit 1
fi
GOLDEN_V="$(ls -t "${IN1}_${IN2}"*"_GenMul.v" | head -n 1)"
if [[ -z "$GOLDEN_V" ]]; then
    echo "ERROR: Golden RTL generation did not produce a file in $OUT_DIR"
    exit 1
fi

# The final generated multiplier module name is not fixed to a single size.
# Read it directly from the RTL so the equivalence check matches the actual design.
GOLDEN_TOP="$(grep -E '^[[:space:]]*module[[:space:]]+' "$GOLDEN_V" | tail -n 1 | sed -E 's/^[[:space:]]*module[[:space:]]+([A-Za-z0-9_]+).*/\1/')"
APPROX_TOP="$(grep -E '^[[:space:]]*module[[:space:]]+' "$APPROX_V" | tail -n 1 | sed -E 's/^[[:space:]]*module[[:space:]]+([A-Za-z0-9_]+).*/\1/')"

if [[ -z "$GOLDEN_TOP" || -z "$APPROX_TOP" ]]; then
    echo "ERROR: Could not determine the top module name from the generated Verilog files."
    exit 1
fi

echo "Generated Golden: $GOLDEN_V"
echo "Golden top: $GOLDEN_TOP"
echo "Approx top: $APPROX_TOP"

if ! command -v yosys &> /dev/null; then
    echo "ERROR: 'yosys' is not installed or not in PATH."
    exit 1
fi
YOSYS_ABC=""
if command -v yosys-abc &> /dev/null; then
    YOSYS_ABC="yosys-abc"
elif command -v abc &> /dev/null; then
    YOSYS_ABC="abc"
fi


# ------------------------------------------------------------------
# Tunables (override from the environment):
#   EQUIV_TIMEOUT       seconds allowed for the yosys equiv_simple heuristic.
#                       Default is 120s for <=32-bit multipliers and 600s for
#                       wider designs, since the miter grows quickly with width.
#   ENABLE_SAT_FALLBACK set to 1 to also run the unbounded yosys SAT proof if
#                       equiv_simple is inconclusive (default 0: off, because
#                       SAT on a multiplier miter can run for a very long time)
#   SAT_TIMEOUT         seconds allowed for that SAT proof. Default is 300s for
#                       smaller sizes and 900s for wider operands.
# ------------------------------------------------------------------
if [[ -z "${EQUIV_TIMEOUT:-}" ]]; then
    if (( IN1 > 32 || IN2 > 32 )); then
        EQUIV_TIMEOUT=600
    else
        EQUIV_TIMEOUT=120
    fi
else
    EQUIV_TIMEOUT="$EQUIV_TIMEOUT"
fi

ENABLE_SAT_FALLBACK="${ENABLE_SAT_FALLBACK:-0}"

if [[ -z "${SAT_TIMEOUT:-}" ]]; then
    if (( IN1 > 32 || IN2 > 32 )); then
        SAT_TIMEOUT=900
    else
        SAT_TIMEOUT=300
    fi
else
    SAT_TIMEOUT="$SAT_TIMEOUT"
fi

echo "Verification time budget: EQUIV_TIMEOUT=${EQUIV_TIMEOUT}s, SAT_TIMEOUT=${SAT_TIMEOUT}s (width=${IN1}x${IN2})"

TIMEOUT=()
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_AVAILABLE=1
else
    TIMEOUT_AVAILABLE=0
fi
run_limited() {  # run_limited <seconds> <cmd...>
    local secs="$1"; shift
    if [[ $TIMEOUT_AVAILABLE -eq 1 ]]; then
        timeout "$secs" "$@"
    else
        "$@"
    fi
}

CEC_RESULT="not run"        # EQUIVALENT | NOT EQUIVALENT | UNDECIDED | UNKNOWN | not run
M1A_RESULT="not run"        # EQUIVALENT | UNPROVEN | TIMED OUT
M1B_RESULT="not run"        # EQUIVALENT | NOT EQUIVALENT | TIMED OUT | ERROR | skipped

# ------------------------------------------------------------------
# Method 2 (runs FIRST): ABC AIG combinational equivalence check (cec)
#   yosys: read -> synth -> flatten -> aigmap -> write_aiger  (x2)
#   abc:   cec golden.aig debug.aig
# This is a complete check and is fast on multipliers, so it is the
# authoritative verdict. yosys-abc's exit code is NOT reliable (always 0),
# so the verdict is read from its printed message.
# ------------------------------------------------------------------
echo ""
echo "=================================================="
echo " 3. ABC AIG Equivalence Check (cec)  [authoritative]"
echo "=================================================="
if [[ -z "$YOSYS_ABC" ]]; then
    echo "SKIPPED: neither 'yosys-abc' nor 'abc' was found in PATH."
else
    GOLDEN_AIG="$LOG_DIR/golden.aig"
    DEBUG_AIG="$LOG_DIR/debug.aig"

    echo "-- Synthesizing golden design to AIG --"
    "${STDBUF[@]}" yosys -p "
        read_verilog $GOLDEN_V
        synth -top $GOLDEN_TOP
        flatten
        aigmap
        write_aiger -map $LOG_DIR/golden.aim $GOLDEN_AIG
    " 2>&1 | tee "$LOG_DIR/cec_golden_synth.log"
    GOLDEN_AIG_EXIT=${PIPESTATUS[0]}

    echo ""
    echo "-- Synthesizing approximate/debug design to AIG --"
    "${STDBUF[@]}" yosys -p "
        read_verilog $APPROX_V
        synth -top $APPROX_TOP
        flatten
        aigmap
        write_aiger -map $LOG_DIR/debug.aim $DEBUG_AIG
    " 2>&1 | tee "$LOG_DIR/cec_debug_synth.log"
    DEBUG_AIG_EXIT=${PIPESTATUS[0]}

    if [[ $GOLDEN_AIG_EXIT -ne 0 || $DEBUG_AIG_EXIT -ne 0 ]]; then
        echo ""
        echo "--- cec RESULT: could not run (AIG synthesis failed) ---"
    else
        echo ""
        echo "-- Running ABC combinational equivalence check (cec) --"
        CEC_LOG="$LOG_DIR/cec.log"
        "${STDBUF[@]}" "$YOSYS_ABC" -c "cec $GOLDEN_AIG $DEBUG_AIG" 2>&1 | tee "$CEC_LOG"

        echo ""
        if grep -qi "NOT EQUIVALENT" "$CEC_LOG"; then
            CEC_RESULT="NOT EQUIVALENT"
            echo "--- cec RESULT: NOT EQUIVALENT ---"
            echo "    See $CEC_LOG for the failing output and counter-example input pattern."
        elif grep -qi "undecided" "$CEC_LOG"; then
            CEC_RESULT="UNDECIDED"
            echo "--- cec RESULT: UNDECIDED (resource limit reached, inconclusive) ---"
        elif grep -qi "are equivalent" "$CEC_LOG"; then
            CEC_RESULT="EQUIVALENT"
            echo "--- cec RESULT: EQUIVALENT ---"
        else
            CEC_RESULT="UNKNOWN"
            echo "--- cec RESULT: UNKNOWN (could not parse ABC's output, see $CEC_LOG) ---"
        fi
    fi
fi

# ------------------------------------------------------------------
# Method 1a: yosys equiv_make / equiv_simple heuristic (time-limited).
# equiv_make pairs up every same-named wire in gold and gate and creates an
# $equiv cell for each. For an approximate design, internal wires such as
# the S output of an approximate full adder are DIFFERENT from the exact
# design's on purpose (later logic compensates), so those pairs can never
# be proven even though the primary outputs match. `rename -hide` strips
# the names from internal wires/cells (ports keep theirs) so only primary
# outputs are compared, which is the question we actually care about.
# equiv_simple is still a bounded heuristic: "failed" means UNPROVEN, not
# "different". It is a cross-check, not authoritative.
# ------------------------------------------------------------------
echo ""
echo "=================================================="
echo " 4. Yosys equiv_make / equiv_simple  [heuristic cross-check, ${EQUIV_TIMEOUT}s limit]"
echo "=================================================="
METHOD1A_LOG="$LOG_DIR/equiv_simple.log"
run_limited "$EQUIV_TIMEOUT" "${STDBUF[@]}" yosys -p "
    read_verilog $GOLDEN_V
    hierarchy -check -top $GOLDEN_TOP
    proc
    flatten
    opt_clean
    rename -hide w:* c:*
    design -stash gold

    design -reset
    read_verilog $APPROX_V
    hierarchy -check -top $APPROX_TOP
    proc
    flatten
    opt_clean
    rename -hide w:* c:*
    design -stash gate

    design -copy-from gold -as gold $GOLDEN_TOP
    design -copy-from gate -as gate $APPROX_TOP
    equiv_make gold gate equiv
    hierarchy -top equiv

    equiv_simple -short
    equiv_simple
    equiv_purge
    equiv_status
" 2>&1 | tee "$METHOD1A_LOG"
M1A_EXIT=${PIPESTATUS[0]}

echo ""
if [[ $M1A_EXIT -eq 124 ]]; then
    M1A_RESULT="TIMED OUT"
    echo "--- equiv_simple RESULT: TIMED OUT after ${EQUIV_TIMEOUT}s (inconclusive) ---"
elif grep -q "Equivalence successfully proven!" "$METHOD1A_LOG"; then
    M1A_RESULT="EQUIVALENT"
    echo "--- equiv_simple RESULT: EQUIVALENT (all \$equiv cells proven) ---"
else
    M1A_RESULT="UNPROVEN"
    echo "--- equiv_simple RESULT: UNPROVEN / INCONCLUSIVE ---"
    echo "    equiv_simple could not prove every \$equiv cell (see the 'Unproven' list in"
    echo "    $METHOD1A_LOG). This does NOT mean the designs differ; ABC cec above is authoritative."
fi

# ------------------------------------------------------------------
# Method 1b (opt-in): unbounded yosys SAT proof on a miter.
# Off by default: SAT solvers struggle badly with multiplier miters and
# this can appear to hang. Enable with ENABLE_SAT_FALLBACK=1.
# ------------------------------------------------------------------
echo ""
echo "=================================================="
echo " 5. Yosys SAT proof  [optional]"
echo "=================================================="
if [[ "$ENABLE_SAT_FALLBACK" != "1" ]]; then
    M1B_RESULT="skipped"
    echo "Skipped (multiplier miters can take extremely long to solve)."
    echo "Enable with:  ENABLE_SAT_FALLBACK=1 [SAT_TIMEOUT=<seconds>] ./run_equiv_check.sh ..."
elif [[ "$M1A_RESULT" == "EQUIVALENT" ]]; then
    M1B_RESULT="skipped"
    echo "Skipped (equiv_simple already proved equivalence)."
else
    METHOD1B_LOG="$LOG_DIR/sat_proof.log"
    echo "Running with a ${SAT_TIMEOUT}s limit..."
    run_limited "$SAT_TIMEOUT" "${STDBUF[@]}" yosys -p "
        read_verilog $GOLDEN_V
        hierarchy -check -top $GOLDEN_TOP
        proc
        flatten
        opt_clean
        design -stash gold

        design -reset
        read_verilog $APPROX_V
        hierarchy -check -top $APPROX_TOP
        proc
        flatten
        opt_clean
        design -stash gate

        design -copy-from gold -as gold $GOLDEN_TOP
        design -copy-from gate -as gate $APPROX_TOP
        miter -equiv -flatten gold gate miter
        hierarchy -top miter
        sat -verify -prove trigger 0 -show-inputs -show-outputs miter
    " 2>&1 | tee "$METHOD1B_LOG"
    M1B_EXIT=${PIPESTATUS[0]}
    echo ""
    if [[ $M1B_EXIT -eq 124 ]]; then
        M1B_RESULT="TIMED OUT"
        echo "--- SAT proof RESULT: TIMED OUT after ${SAT_TIMEOUT}s (inconclusive) ---"
    elif [[ $M1B_EXIT -eq 0 ]]; then
        M1B_RESULT="EQUIVALENT"
        echo "--- SAT proof RESULT: EQUIVALENT ---"
    elif grep -q "Called with -verify and proof did fail" "$METHOD1B_LOG"; then
        M1B_RESULT="NOT EQUIVALENT"
        echo "--- SAT proof RESULT: NOT EQUIVALENT (genuine counter-example) ---"
    else
        M1B_RESULT="ERROR"
        echo "--- SAT proof RESULT: ERROR (exit $M1B_EXIT, see $METHOD1B_LOG) ---"
    fi
fi

# ------------------------------------------------------------------
# Summary / verdict
#   1. Any complete check that found a counter-example -> NOT EQUIVALENT.
#   2. Otherwise any complete check that proved it (ABC cec, or the SAT
#      proof) -> EQUIVALENT.
#   3. equiv_simple alone proving it is also accepted.
#   4. Otherwise -> INCONCLUSIVE.
# ------------------------------------------------------------------
echo ""
echo "=================================================="
echo " Summary"
echo "=================================================="
echo " ABC cec (authoritative)     : $CEC_RESULT"
echo " Yosys equiv_simple          : $M1A_RESULT"
echo " Yosys SAT proof (optional)  : $M1B_RESULT"
echo " Full logs saved under: $LOG_DIR"
echo "=================================================="

VERDICT="INCONCLUSIVE"
if [[ "$CEC_RESULT" == "NOT EQUIVALENT" || "$M1B_RESULT" == "NOT EQUIVALENT" ]]; then
    VERDICT="NOT EQUIVALENT"
elif [[ "$CEC_RESULT" == "EQUIVALENT" || "$M1B_RESULT" == "EQUIVALENT" || "$M1A_RESULT" == "EQUIVALENT" ]]; then
    VERDICT="EQUIVALENT"
fi

echo ""
echo "=================================================="
case "$VERDICT" in
    EQUIVALENT)     echo " Flow Complete Successfully! (EQUIVALENT)"; RC=0 ;;
    "NOT EQUIVALENT") echo " Flow Complete - NOT EQUIVALENT"; RC=1 ;;
    *)              echo " Flow INCONCLUSIVE - no check completed a decisive proof"; RC=2 ;;
esac
echo "=================================================="
exit $RC