#include "VerilogGen.hpp"
#include <assert.h>
#include <iostream>
#include <ApproxConfig.hpp>

vector<int> Array(map<int, int> Ins, int nIn1, int nIn2, string &file, bool sign, int approxColumn = -1, int approxMethod = 2, bool debugMode = false);