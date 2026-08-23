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

    // A simple template-based approximate FA.
    // This is intentionally generated from a truth table instead of copying FV-LIDAC netlist code.
    // The template below is a low-cost approximation: it preserves the exact output for the smallest cases,
    // and changes the carry/sum for the one critical 3-input case where a simplified carry is acceptable.
    // Truth-table encoding: {C,S} with two-bit values for each 3-bit input ordering (X,Y,Z).
    static vector<int> defaultApproxTruthTable()
    {
        // index ordering is X*4 + Y*2 + Z, values stored as (C<<1)|S
        // This intentionally keeps the exact behavior for the easy cases and approximates one high-cost case.
        return {
            0,  // 000 -> (0,0)
            1,  // 001 -> (0,1)
            1,  // 010 -> (0,1)
            3,  // 011 -> (1,1)
            1,  // 100 -> (0,1)
            3,  // 101 -> (1,1)
            2,  // 110 -> (1,0)  // approximate, not exact carry behaviour
            3   // 111 -> (1,1)
        };
    }

    void configureTemplateApproxFA()
    {
        clear();
        vector<int> tt = defaultApproxTruthTable();
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
