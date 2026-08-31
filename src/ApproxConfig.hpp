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

    // returns module name or empty string
    string getModuleForWeight(int weight);
    // returns map moduleName -> truthTable
    map<string, vector<int>> getModulesMap();

    // Sayak: Mask based configuration for approximate full adder ckt
    vector<int> truthTableFromMasks(int coutMask, int sumMask);
    void configureApproxFA(int column, int coutMask, int sumMask);

}

#endif
