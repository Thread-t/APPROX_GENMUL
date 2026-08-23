#ifndef FVIMPORTER_HPP
#define FVIMPORTER_HPP

#include <string>

using namespace std;

// Parse a FV-LIDAC-style Verilog netlist and register approximate FA modules
bool importFVPreset(const string &filePath);

#endif
