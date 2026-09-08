#include "ApproxConfig.hpp"

namespace ApproxConfig {

    static map<int, string> weightToModule;
    static map<string, vector<int>> modules;

    // Maps weight -> revert module name (populated by enableDebugMode())
    static map<int, string> weightToRevertModule;
    static map<string, vector<int>> revertModules;

    void clear()
    {
        weightToModule.clear();
        modules.clear();
        weightToRevertModule.clear();
        revertModules.clear();
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

    // Returns the truth table of the exact 3-input full adder.
    // Input index i = (X<<2)|(Y<<1)|Z; output = (Cout<<1)|Sum.
    vector<int> exactFATruthTable()
    {
        vector<int> tt(8);
        for (int i = 0; i < 8; ++i)
        {
            int X = (i >> 2) & 1;
            int Y = (i >> 1) & 1;
            int Z =  i       & 1;
            int sum  = X ^ Y ^ Z;
            int cout = (X & Y) | (Y & Z) | (Z & X);
            tt[i] = (cout << 1) | sum;
        }
        return tt;
    }

    // Revert-cell truth table: revert[i] = exact[i] XOR approx[i] (per bit).
    // When the revert cell's Sum/Cout outputs are XOR'd with the approx cell's
    // Sum/Cout outputs, the result equals the exact full-adder output.
    vector<int> revertTruthTable(const vector<int> &approxTT)
    {
        vector<int> exact = exactFATruthTable();
        vector<int> rv(8);
        for (int i = 0; i < 8; ++i)
        {
            // XOR each of the two output bits independently
            rv[i] = exact[i] ^ approxTT[i];
        }
        return rv;
    }

    // Returns the revert module name for a given weight, or empty string if none.
    string getRevertModuleForWeight(int weight)
    {
        auto it = weightToRevertModule.find(weight);
        if (it == weightToRevertModule.end())
            return string("");
        return it->second;
    }

    // Returns the map of revert module names to their truth tables.
    map<string, vector<int>> getRevertModulesMap()
    {
        return revertModules;
    }

    // Derives revert-module name from approx module name by replacing prefix.
    static string makeRevertModuleName(const string &approxName)
    {
        // approx name format: "approx_fa_<coutMask>_<sumMask>"
        // revert name format: "revert_fa_<coutMask>_<sumMask>"
        string rv = approxName;
        if (rv.substr(0, 7) == "approx_")
            rv = "revert_" + rv.substr(7);
        else
            rv = "revert_" + rv;
        return rv;
    }

    // Enables debug mode: for every registered approx module, register its
    // corresponding revert module so that GenerateRevertModules() can emit it.
    void enableDebugMode()
    {
        for (auto &wm : weightToModule)
        {
            int weight = wm.first;
            const string &approxName = wm.second;
            const vector<int> &approxTT = modules[approxName];

            string rvName = makeRevertModuleName(approxName);
            vector<int> rvTT = revertTruthTable(approxTT);

            weightToRevertModule[weight] = rvName;
            if (revertModules.find(rvName) == revertModules.end())
                revertModules[rvName] = rvTT;
        }
    }

}
