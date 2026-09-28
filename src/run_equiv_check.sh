# Combinational equivalence check: exact GenMul multiplier vs approx+revert version
# Requires the *renamed* gate netlist, so that equiv_make can match internal nodes by name.
#
#   yosys equiv_check.ys

# ---------- golden ----------
read_verilog 16_16_U_SP_DT_RC_GenMul.v
hierarchy -check -top Mult_16_16
proc
flatten
opt_clean
design -stash gold

# ---------- gate (approx + revert, renamed) ----------
design -reset
read_verilog 16_16_U_SP_ADT_RC_M2_COL12_C51_S12_DEBUG_GenMul.v
hierarchy -check -top Mult_16_16
proc
flatten
opt_clean
design -stash gate

# ---------- miter ----------
design -copy-from gold -as gold Mult_16_16
design -copy-from gate -as gate Mult_16_16
equiv_make gold gate equiv
hierarchy -top equiv

# Prove the easy (local) points first, then widen the cones.
equiv_simple -short
equiv_simple
equiv_purge
equiv_status -assert
