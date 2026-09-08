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

    // Sayak: Mask based configuration for approximate full adder ckt.
    // The approximation is applied to all lower Dadda columns from 0 up to approxColumn.
    vector<int> truthTableFromMasks(int coutMask, int sumMask);
    void configureApproxFA(int approxColumn, int coutMask, int sumMask);

    // --- DEBUG / FVLIDAC revert-cell support ---
    // Returns the truth table of the exact full adder (standard majority/XOR).
    vector<int> exactFATruthTable();

    // Computes the revert-cell truth table for a given approx truth table:
    //   revert[i] = exact[i] XOR approx[i]  (independently for Cout bit and Sum bit)
    vector<int> revertTruthTable(const vector<int> &approxTT);

    // Returns the revert module name for a given weight's approx module, or "" if none.
    string getRevertModuleForWeight(int weight);

    // Returns map revertModuleName -> revertTruthTable (populated when debugMode is on).
    map<string, vector<int>> getRevertModulesMap();

    // Enables debug mode: for every approx module registered, also register its revert module.
    void enableDebugMode();
}

#endif
