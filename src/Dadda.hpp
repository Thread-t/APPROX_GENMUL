#include "VerilogGen.hpp"
#include <assert.h>
#include <iostream>

vector<int> Dadda(map<int, int> Ins, int nIn1, int nIn2, string &file);
// Approximate Dadda with configurable method:
// approxMethod: 0=exact, 1=truncation only, 2=FA substitution only, 3=both
// approxColumn: apply FA approximation only to columns 0 .. approxColumn-1
vector<int> ApproxDadda(map<int, int> Ins, int nIn1, int nIn2, string &file, int approxColumn, int approxMethod = 3);
