#include "ApproxConfig.hpp"

namespace ApproxConfig {

    static map<int, string> weightToModule;
    static map<string, vector<int>> modules;
    //static int lastTruncateBits = 0;

    void clear()
    {
        weightToModule.clear();
        modules.clear();
        //lastTruncateBits = 0;
    }

    //void setLastTruncateBits(int bits) { lastTruncateBits = bits; }
    //int getLastTruncateBits() { return lastTruncateBits; }

    // Helper function to generate a unique module name based on the truth table
    // static string makeModuleName(const vector<int> &tt)
    // {
    //     unsigned long long id = 0;
    //     // Each entry in the truth table is a 2-bit value (C,S) for the 3-bit input index {X,Y,Z}
    //     for (int i = 0; i < (int)tt.size(); ++i)
    //     {
    //         // Each entry is in [0..3], so we can encode
    //         // the entire truth table as a single integer
    //         id = id * 4 + (tt[i] & 3);
    //     }
    //     return string("approx_fa_") + to_string(id);
    // }

    //Sayak: Make the module name more interpretable by encoding the carry and sum masks separately.
    static string makeModuleName(const vector<int> &tt)
    {
        int coutMask = 0;
        int sumMask = 0;

        for (int input = 0; input < 8; ++input)
        {
            coutMask = (coutMask << 1) | ((tt[input] >> 1) & 1);
            sumMask  = (sumMask << 1)  | (tt[input] & 1);
        }

        return "approx_fa_" + to_string(coutMask) + "_" + to_string(sumMask);
    }


    // Exact full-adder truth table.
    // Encoding is {C,S} by index order X*4 + Y*2 + Z.
    // vector<int> exactFATruthTable()
    // {
    //     return {0, 1, 1, 2, 1, 2, 2, 3};
    // }

    // Sayak: Generate a truth table from carry and sum masks.
    vector<int> truthTableFromMasks(int coutMask, int sumMask)
    {
        vector<int> tt(8);

        // Bit 7 corresponds to input 000; bit 0 corresponds to input 111.
        for (int input = 0; input < 8; ++input)
        {
            int c = (coutMask >> (7 - input)) & 1;
            int s = (sumMask  >> (7 - input)) & 1;
            tt[input] = (c << 1) | s;
        }

        return tt;
    }

    void configureApproxFA(int column, int coutMask, int sumMask)
    {
        clear();

        vector<int> tt = truthTableFromMasks(coutMask, sumMask);

        // Replace full adders in one selected Dadda column only.
        // FullAdder::returnVerilogCode() applies this module in every
        // reduction stage that contains this column.
        setApproxForWeight(column, tt);
    }

    // sayak: Apply a controlled number of bit distortions to the exact FA truth table.
    // The function takes a list of truth-table indices to modify and a list of
    // replacement values. This keeps the approximation modular and can be reused for
    // exact, one-bit-error, two-bit-error, and higher-order FA variants.
    // static vector<int> applyTruthTableErrors(const vector<int> &base, const vector<int> &indices, const vector<int> &newValues)
    // {
    //     vector<int> tt = base;
    //     int count = min((int)indices.size(), (int)newValues.size());
    //     for (int i = 0; i < count; ++i)
    //     {
    //         // Ensure the index is valid before applying the error
    //         if (indices[i] >= 0 && indices[i] < (int)tt.size())
    //         {
    //             tt[indices[i]] = newValues[i];
    //         }
    //     }
    //     return tt;
    // }

    // vector<int> oneBitErrorFATruthTable()
    // {
    //     vector<int> tt = exactFATruthTable();
    //     // Distort only a single critical case: 110 from (1,0) to (1,1)
    //     // which changes the carry/sum pattern slightly without making the FA extremely inaccurate.
    //     return applyTruthTableErrors(tt, {6}, {3});
    // }

    // vector<int> twoBitErrorFATruthTable()
    // {
    //     vector<int> tt = exactFATruthTable();
    //     // Distort 110 and 111 to create a moderate approximate FA.
    //     return applyTruthTableErrors(tt, {6, 7}, {3, 2});
    // }

    // vector<int> nBitErrorFATruthTable(int bitErrorCount)
    // {
    //     vector<int> tt = exactFATruthTable();
    //     switch (bitErrorCount)
    //     {
    //         case 0:
    //             return tt;
    //         case 1:
    //             return oneBitErrorFATruthTable();
    //         case 2:
    //             return twoBitErrorFATruthTable();
    //         default:
    //         {
    //             // Higher-order approximation: distort several critical cases.
    //             // This is still modular and derived from the same exact FA table.
    //             return applyTruthTableErrors(tt, {3, 5, 6, 7}, {2, 1, 3, 2});
    //         }
    //     }
    // }

    // vector<int> defaultApproxTruthTable(int errorLevel)
    // {
    //     return nBitErrorFATruthTable(errorLevel);
    // }

    // void configureTemplateApproxFA(int errorLevel, int maxApproxWeight)
    // {
    //     clear();
    //     vector<int> tt = defaultApproxTruthTable(errorLevel);

    //     // Approximate only the low-significance columns.
    //     // This follows the typical FV-LIDAC idea: keep the higher columns exact and
    //     // simplify only the earliest bit positions where the error is less impactful.
    //     // For example, maxApproxWeight = 4 gives weights {1, 2, 4}.
    //     for (int weight = 1; weight <= maxApproxWeight; weight++)
    //     {
    //         setApproxForWeight(weight, tt);
    //     }
    // }
    
    // Set the approximate full-adder truth table for a given weight
    string setApproxForWeight(int weight, const vector<int> &truthTable)
    {
        if (truthTable.size() != 8)
            return string("");
        string name = makeModuleName(truthTable);
        // store module if not present
        if (modules.find(name) == modules.end())
            modules[name] = truthTable;
        weightToModule[weight] = name;
        return name;
    }

    // Get the module name for a given weight, or empty string if not set
    string getModuleForWeight(int weight)
    {
        auto it = weightToModule.find(weight);
        if (it == weightToModule.end())
            return string("");
        return it->second;
    }

    // Get the map of module names to their truth tables
    map<string, vector<int>> getModulesMap()
    {
        return modules;
    }

}
