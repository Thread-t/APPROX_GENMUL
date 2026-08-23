#ifndef APPROXCONFIG_HPP
#define APPROXCONFIG_HPP

#include <string>
#include <vector>
#include <map>

using namespace std;

// Store approximate full-adder truth tables and mapping from weight -> module name.
namespace ApproxConfig {
    void clear();
    // truthTable: 8 entries, each in [0..3] encoding (C<<1)|S for input index {X,Y,Z}
    string setApproxForWeight(int weight, const vector<int> &truthTable);
    // errorLevel: 0 = exact, 1 = low error, 2 = medium error, 3 = high error
    void configureTemplateApproxFA(int errorLevel = 1);
    vector<int> defaultApproxTruthTable(int errorLevel = 1);
    // returns module name or empty string
    string getModuleForWeight(int weight);
    // returns map moduleName -> truthTable
    map<string, vector<int>> getModulesMap();
}

#endif
