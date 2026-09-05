#include "VerilogGen.hpp"
#include <assert.h>
#include <iostream>

using namespace std;

// Get two integer numbers as input sizes and create the ripple carry adder
// Sayak : Add one more argument : by default -1 to indicate approximation is disabled
int CreateRippleCarryAdder(int nIn1, int nIn2, string &file, int approxColumn = -1); 