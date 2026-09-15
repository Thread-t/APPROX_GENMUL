#!/bin/bash
# Automatically generated script for Yosys equivalence checking
# Location: sayakdeb@eduroam-pool12-1219 src %
# Change the name of the gold and gate verilog files as needed

yosys -Q -p '
  design -reset;
  read_verilog 8_8_U_SP_DT_RC_GenMul.v;
  rename Mult_8_8 gold;
  hierarchy -top gold;
  flatten gold;
  design -stash gold_space;

  design -reset;
  read_verilog 8_8_U_SP_ADT_RC_M2_COL10_C10_S170_DEBUG_GenMul.v;
  rename Mult_8_8 gate;
  hierarchy -top gate;
  flatten gate;
  design -stash gate_space;

  design -copy-from gold_space gold;
  design -copy-from gate_space gate;

  equiv_make gold gate equiv;
  equiv_simple;
  equiv_induct equiv;
  equiv_status -assert equiv
'
