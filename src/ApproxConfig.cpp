#include "ApproxConfig.hpp"

namespace ApproxConfig {

    static map<int, string> weightToModule;
    static map<string, vector<int>> modules;

    void clear()
    {
        weightToModule.clear();
        modules.clear();
    }

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

    // Sayak: Generate a truth table from carry and sum masks.
    vector<int> truthTableFromMasks(int coutMask, int sumMask)
    {
        vector<int> tt(8);

        // Bit 7 corresponds to input 000; bit 0 corresponds to input 111.
        for (int input = 0; input < 8; ++input)
        {
            // The masks are in reverse order: bit 7 is for input 000, 
            // bit 0 is for input 111.
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
