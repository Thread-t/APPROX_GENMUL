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

    // Generator family for approximate full adders.
    // Exact FA: 0 bit errors.
    // One-bit-error FA: 1 bit distortion in the truth table.
    // Two-bit-error FA: 2 bit distortions in the truth table.
    // etc.
    // vector<int> exactFATruthTable();
    // vector<int> oneBitErrorFATruthTable();
    // vector<int> twoBitErrorFATruthTable();
    // vector<int> nBitErrorFATruthTable(int bitErrorCount);

    // Backward-compatible API.
    // The approximation is intentionally restricted to low-significance columns.
    // Example: maxApproxWeight = 4 means only weights 1, 2, and 4 are approximated.
   // void configureTemplateApproxFA(int errorLevel = 1, int maxApproxWeight = 4);
   // vector<int> defaultApproxTruthTable(int errorLevel = 1);

    // returns module name or empty string
    string getModuleForWeight(int weight);
    // returns map moduleName -> truthTable
    map<string, vector<int>> getModulesMap();

    // Sayak: Mask based configuration for approximate full adder ckt
    vector<int> truthTableFromMasks(int coutMask, int sumMask);
    void configureApproxFA(int column, int coutMask, int sumMask);

    // // to track the truncate bits
    // void setLastTruncateBits(int bits);
    // int getLastTruncateBits();
}

#endif
