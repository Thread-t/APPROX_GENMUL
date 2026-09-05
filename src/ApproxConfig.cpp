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

    // Sayak: Generate a truth table from carry and sum masks for three inouts.
    vector<int> truthTableFromMasks(int coutMask, int sumMask)
    {
        vector<int> tt(8);

        //Sayak: Bit 7 corresponds to input 000; bit 0 corresponds to input 111. I am running the loop from 0 - 7
        for (int input = 0; input < 8; ++input)
        {
            int c = (coutMask >> (7 - input)) & 1;
            int s = (sumMask  >> (7 - input)) & 1;
            tt[input] = (c << 1) | s;
        }

        return tt;
    }

    // Sayak: Configure the approximate full adder for all Dadda columns below a given limit.
    // Only the lower columns [0 ... approxColumn] are approximated; all columns >= approxColumn are exact.
    void configureApproxFA(int approxColumn, int coutMask, int sumMask)
    {
        clear();

        vector<int> tt = truthTableFromMasks(coutMask, sumMask);

        // Approximate every Dadda column below the requested limit. This matches the intended
        // behavior where the lower columns are more error-tolerant while higher columns stay exact.
        for (int column = 0; column <= approxColumn; ++column)
        {
            setApproxForWeight(column, tt);
        }
    }
    
    // Set the approximate full-adder truth table for a given weight
    string setApproxForWeight(int weight, const vector<int> &truthTable)
    {
        if (truthTable.size() != 8)
            return string("");

        // Generate a unique module name based on the truth table
        string name = makeModuleName(truthTable);

        // store module if not present
        if (modules.find(name) == modules.end())
            modules[name] = truthTable;

        // store mapping from weight to module name
        weightToModule[weight] = name;
        return name;
    }

    // Sayak: Get the module name for a given weight, or empty string if not set
    string getModuleForWeight(int weight)
    {
        auto it = weightToModule.find(weight);
        if (it == weightToModule.end())
            return string("");
        return it->second;
    }

    // Sayak: Get the map of module names to their truth tables
    map<string, vector<int>> getModulesMap()
    {
        return modules;
    }

}
