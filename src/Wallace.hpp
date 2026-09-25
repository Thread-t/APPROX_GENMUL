#include "VerilogGen.hpp"
#include <assert.h>
#include <iostream>

vector<int> Wallace(map<int, int> Ins, int nIn1, int nIn2, string &file);
vector<int> ApproxWallace(map<int, int> Ins, int nIn1, int nIn2, string &file,
                         int approxColumn, int approxMethod = 3, bool debugMode = false);