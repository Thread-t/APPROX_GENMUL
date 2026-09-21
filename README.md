[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# GenMul (version 1)

GenMul is a multiplier generator which outputs multiplier circuits in Verilog. The input size of a multiplier and each multiplier stage can be configured with GenMul. For more information visit [www.sca-verification.org](http://www.sca-verification.org). There you can also run GenMul via Browser.

## Clone

Clone GenMul using:

```bash
git clone https://github.com/amahzoon/genmul.git
```

## Installation (shell interface)

To build GenMul binary:

```bash
mkdir build
cd build
cmake ..
make install -j2
```

After installation, GenMul can be run from `bin/genmul`. 

## Installation (Emscripten)

[Emscripten](https://emscripten.org/) toolchain can be used to compile JavaScript from our C++ implementation of GenMul.

```bash
mkdir build
cd build
emcmake cmake ..
emmake make install -j2
```

The compiled files are accessible through `bin/genmul.js` and `bin/genmul.wasm`.

Currecntly, we have used the compiled javaScript files in the [web-based version of Genmul](http://www.sca-verification.org/genmul).

## Getting Started

```bash
./genmul
```

After running, GenMul asks you to choose the architectures for the Partial Product Generator (PPG), Partial Product Accumulator (PPA), and Final Stage Adder (FSA), respectively. Then, the bit sizes of the first and second inputs have to be set. Finally, the Verilog file of the multiplier is generated.

To generate an exact (non-approximate) multiplier, choose any PPA option other than `5` (Approximate Dadda tree) — options `1`–`4` produce a fully exact circuit and none of the approximate-mode prompts below are shown:

## Note:
You can also select PPA option `5` and then set the approximation method to `0` (exact) at the corresponding prompt — this also yields a fully exact circuit, just routed through the Approximate Dadda tree code path rather than the plain Dadda tree. This is a failsafe mechanism i added.

## For Using Approximate Mode
Selecting PPA option `5` (Approximate Dadda tree) unlocks a set of additional prompts that let you inject a single custom approximate full-adder truth table into the reduction pipeline, following the FV-LIDAC style of approximation.

You will then be asked for:
- **How many columns to approximate**: the number of low-to-mid significance bit-columns (starting from column 0, the least significant) that should use the approximate full adder instead of the exact one, in every reduction stage they pass through — the Dadda tree and the final-stage adder (for our case RC).

- **Carry truth-table mask (0..255)** and **Sum truth-table mask (0..255)**: each is an 8-bit mask describing the approximate full adder's truth table. Bit 7 (MSB) corresponds to input pattern `XYZ=000`, down to bit 0 (LSB) for `XYZ=111`; a `1` bit means that output is asserted for that input pattern. The exact full adder's truth table corresponds to carry mask `23` and sum mask `105` (derived from `C = majority(X,Y,Z)`, `S = X⊕Y⊕Z`, encoded MSB-first as described above); any other pair of masks introduces some degree of intentional approximation.

- **Approximation method**: `0` = exact (no substitution), `1` = truncation only, `2` = FA-substitution only (the approximate cell described above), `3` = both truncation and FA-substitution combined. 
Please use the mode 2 always. I implemented mode 1(removal of lower weight PPGs) and mode 3 initially but those are not fully fuctional.

- **Using the Debug mode**:
After the approximation prompts, you will be asked:
DEBUG mode - FVLIDAC revert cell (0=off,1=on): 

Enabling DEBUG mode (`1`) pairs every approximate full-adder cell with a matching **revert cell** that undoes the introduced error, so the overall generated netlist is functionally identical to the exact multiplier — despite containing the approximate cells internally. This is intended purely for verification: it lets you confirm, via equivalence checking, that the approximate-cell substitution and column/wire routing logic in GenMul itself is wired correctly, independent of whether the approximation's numerical error is behaving as expected. 

Output files generated in DEBUG mode are marked with a `_DEBUG` suffix, e.g. `8_8_U_SP_ADT_RC_M2_COL10_C51_S12_DEBUG_GenMul.v`.

Leaving DEBUG mode off (`0`) generates the actual approximate circuit, with the numerical error intact, intended for downstream error-metric and design-metric evaluation.

- **DEBUG-mode files** (approximate cell + revert cell): equivalence checking should report the netlist as functionally equivalent to the exact multiplier, since the revert cell is designed to cancel out the approximate cell's error. A pass here confirms GenMul's column selection and wiring are correct.
- **Normal, non-approximated files** (PPA options `1`–`4`, or PPA `5` with approximation method `0`): equivalence checking against a reference exact multiplier should likewise report equivalence, since these circuits contain no intentional approximation.

Files generated with approximation method `1`, `2`, or `3` and DEBUG mode off are *expected* to fail equivalence checking against the exact reference — that mismatch is the intended, measurable approximation error, not a bug.

## For Equivalence Check
We use Yosys's `equiv_simple` mode to check both categories of generated RTL:
we need to change the generated RTL file names accordingly to make the script i.e 'run_equiv_check.sh' work.
# ---------- golden ----------
read_verilog 16_16_U_SP_DT_RC_GenMul.v   <-- The RTL code without approximation


# ---------- gate (approx + revert, renamed) ----------
design -reset
read_verilog 16_16_U_SP_ADT_RC_M2_COL12_C51_S12_DEBUG_GenMul.v   <-- The RTL code generated with DEBUG mode on

I have added a Yosys script to compare the generated RTL (with DEBUG mode enabled) against the error-free golden model.You can run the equivalence check from the directory containing both RTL files using the following command:

yosys -s ../../src/run_equiv_check.sh
