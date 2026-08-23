#include "ApproxConfig.hpp"

namespace ApproxConfig {

    static map<int, string> weightToModule;
    static map<string, vector<int>> modules;

    void clear()
    {
        weightToModule.clear();
        modules.clear();
    }

    // Helper function to generate a unique module name based on the truth table
    static string makeModuleName(const vector<int> &tt)
    {
        unsigned long long id = 0;
        // Each entry in the truth table is a 2-bit value (C,S) for the 3-bit input index {X,Y,Z}
        for (int i = 0; i < (int)tt.size(); ++i)
        {
            // Each entry is in [0..3], so we can encode
            // the entire truth table as a single integer
            id = id * 4 + (tt[i] & 3);
        }
        return string("approx_fa_") + to_string(id);
    }

    // A template-based approximate FA.
    // This is intentionally generated from a truth table instead of copying FV-LIDAC netlist code.
    // We keep the same 3-input full-adder structure, but deliberately alter a few high-impact cases
    // to create a controllable error level. The encoding is {C,S} by index order X*4 + Y*2 + Z.
    vector<int> defaultApproxTruthTable(int errorLevel)
    {
        // Exact full-adder truth table:
        // 000 -> 0, 001 -> 1, 010 -> 1, 011 -> 3,
        // 100 -> 1, 101 -> 3, 110 -> 2, 111 -> 3
        vector<int> tt = {0, 1, 1, 3, 1, 3, 2, 3};

        switch (errorLevel)
        {
            case 0:
                return tt; // exact
            case 1:
                // Low-error approximation: flip the 110 case from (1,0) to (1,1)
                // This produces a small carry/sum distortion while keeping most outputs exact.
                tt[6] = 3;
                return tt;
            case 2:
                // Medium-error approximation: also distort the 111 case from (1,1) to (1,0)
                tt[6] = 3;
                tt[7] = 2;
                return tt;
            case 3:
                // High-error approximation: aggressively distort the critical sums/carries
                // for 011, 101, 110, and 111.
                tt[3] = 1;
                tt[5] = 1;
                tt[6] = 3;
                tt[7] = 2;
                return tt;
            default:
                return tt;
        }
    }

    void configureTemplateApproxFA(int errorLevel)
    {
        clear();
        vector<int> tt = defaultApproxTruthTable(errorLevel);
        setApproxForWeight(1, tt);
        setApproxForWeight(2, tt);
        setApproxForWeight(4, tt);
    }
    
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
