#include "Dadda.hpp"
#include "ApproxConfig.hpp"

#define UNUSED(x) (void)(x)

static vector<int> DaddaCore(map<int, int> Ins, int nIn1, int nIn2, string &file, const string &typeName, int truncateBits, int approxColumn = -1)
{
    UNUSED(nIn1);
    UNUSED(nIn2);

    int inputNumber = 0;
    vector<PartialProduct> partialIn; //to store the all partial products
    
    for (auto i = 0u; i < Ins.size(); i++)
    {
        for (int j = 0; j < Ins[i]; j++)
        {
            PartialProduct p(i);
            // Sayak: The input partial products are generated based on the 
            // weights specified in the Ins map.
            partialIn.push_back(p);
            inputNumber++;
        }
    }

    // Sayak: If truncation is enabled (truncateBits > 0), we filter out 
    // partial products with weights less than truncateBits and adjust the 
    // weights of the remaining partial products accordingly.
    if (truncateBits > 0)
    {
        vector<PartialProduct> truncatedIn;
        for (auto &p : partialIn)
        {
            if (p.returnWeight() < truncateBits)
            {
                continue;
            }
            p.ChangeWeight(p.returnWeight() - truncateBits);
            truncatedIn.push_back(p);
        }
        partialIn = truncatedIn;
    }
    /////////////////

    vector<PartialProduct> partialOut; //the array of partial products for the output
    vector<Component *> compList;      //the array of used components during implementation

    map<int, vector<PartialProduct>> LevelizedPartials;                //for hashing partial products based on the weights
    PartialProduct::LevelizePartials(LevelizedPartials, partialIn);    //adding the first input to the levelized hash

    Component *comp;  //a temp component to store a just created component

    //we should find the maximum hight of the partial product tree
    unsigned int maxh = 0;  //h will show the max height
    for (auto i: LevelizedPartials)
    {
        if (i.second.size()>maxh)
            maxh = i.second.size();
    }

    int d = 2;           //d parameter in dadda algorithm
    vector<int> D = {d}; //a vector to store all possible d parameters

    bool stopFlag = false;  //a flag to determine when the loop should be stoped

    while (!stopFlag)
    {
        d = 1.5 * d;
        D.push_back(d);
        //if ((1.5 * d) > nIn1 || (1.5 * d) > nIn2)
        if ((1.5 * d) > maxh)
            stopFlag = true;
    }
    reverse(D.begin(), D.end());

    map<int, int> height;  //to keep the track of the heights during dadda reduction

    for (auto i : LevelizedPartials)
    {
        height[i.first] = i.second.size();
    }

    vector<PartialProduct> GeneratedAtLevel;  //all partial products generated a level of wallce tree computations
    int stage = 1;
    for (auto n = 0u; n < D.size(); n++)
    {
        // Sayak: The following loop implements the Dadda reduction for each column of the partial product tree.
        // The reduction is performed until the height of each column is less than or equal to the corresponding D[n] value
        for (auto i = 0u; i < LevelizedPartials.size(); i++)
        {
            while (1)
            {
                // The following logic checks the height of the current column and 
                // applies the appropriate reduction operation (HalfAdder or FullAdder) 
                // based on the height and the Dadda threshold.
                if (height[i] <= D[n])
                {
                    break;
                }
                else if (height[i] == D[n] + 1)
                {
                    // If the height is exactly one more than the target D[n], 
                    // we can use a half-adder to reduce it.
                    height[i]--;
                    height[i + 1]++;

                    // Sayak: The useApproxFA flag determines whether to use an approximate full adder based on the
                    // specified approximation column and the availability of an approximate module for the current weight.
                    const bool useApproxFA = approxColumn >= 0 && static_cast<int>(i) <= approxColumn &&
                                             !ApproxConfig::getModuleForWeight(i).empty();

                    
                    if (approxColumn >= 0)
                    {
                        comp = new FullAdder({LevelizedPartials[i][0], LevelizedPartials[i][1]},
                                              useApproxFA, true);
                    }
                    else
                    {
                        comp = new HalfAdder({LevelizedPartials[i][0], LevelizedPartials[i][1]});
                    }
                    comp->SetOutputs();
                    LevelizedPartials[i].erase(LevelizedPartials[i].begin(), LevelizedPartials[i].begin() + 2);
                    compList.push_back(comp);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[0]);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[1]);
                    break;
                }
                else
                {
                    // The reference library approximates only the low Dadda columns; columns at/above
                    // approxColumn remain exactly reduced using standard FullAdders.
                    const bool approxThisColumn = (approxColumn >= 0 && static_cast<int>(i) <= approxColumn);
                    const bool useApproxFA = approxThisColumn && !ApproxConfig::getModuleForWeight(i).empty();

                    height[i] -= 2;
                    height[i + 1]++;

                    comp = new FullAdder({LevelizedPartials[i][0], LevelizedPartials[i][1], LevelizedPartials[i][2]}, useApproxFA);
                    comp->SetOutputs();
                    LevelizedPartials[i].erase(LevelizedPartials[i].begin(), LevelizedPartials[i].begin() + 3);
                    compList.push_back(comp);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[0]);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[1]);
                }
            }
        }
        PartialProduct::LevelizePartials(LevelizedPartials, GeneratedAtLevel);
        GeneratedAtLevel.clear();
        stage++;
    }

    //Some of the input partial product needs to go directely to output, so we connect them with a = b assignment!
    for (auto &i : LevelizedPartials)
    {
        for (auto &j : i.second)
        {
            if (j.returnNo() < inputNumber)
            {
                comp = new BUF({j});
                comp->SetOutputs();
                j = comp->returnOutputs()[0];
                compList.push_back(comp);
            }
        }
    }
    ////////////////////

    vector<PartialProduct> OutPar1;  //this output is always has more bits
    vector<PartialProduct> OutPar2;
    //for determining the size of the two outputs
    int singleBitNumber = 0;
    int nOut1 = 0;
    int nOut2 = 0;
    for (auto i : LevelizedPartials)
    {
        if (i.second.size() == 1)
            nOut1++;
        else if (i.second.size() == 2)
        {
            nOut1++;
            nOut2++;
        }
    }
    
    //to count the number of the single output that should directely go to the final output
    for (auto i = 0u; i < LevelizedPartials.size(); i++)
    {
        if (LevelizedPartials[i].size() == 1)
            singleBitNumber++;
        else
            break;
    }
    
    //for Collecting two final numbers as outputs
    for (auto i = 0u; i < LevelizedPartials.size(); i++)
    {
        if (LevelizedPartials[i].size() == 1)
            OutPar1.push_back(LevelizedPartials[i][0]);
        if (LevelizedPartials[i].size() == 2)
        {
            OutPar1.push_back(LevelizedPartials[i][0]);
            OutPar2.push_back(LevelizedPartials[i][1]);
        }
    }

    //Generating the output verilog file
    GenerateHeader(Ins.size(), typeName, file);
    GenereateInOutSig(Ins, nOut1, nOut2, file);
    vector<int> signalIDs = Component::collectIDs(compList);
    map<int, string> wireHash = generateWires(Ins, signalIDs, OutPar1, OutPar2, file);
    GenerateComponents(wireHash, compList, file);
    file += "endmodule\n";
    return {(int)OutPar1.size(), (int)OutPar2.size(), singleBitNumber};  //the first and second members are the size of out1 and out2, respectively, and the third output is the number pf single bits at the begining
}

//Sayak: The following function implements the Dadda multiplier algorithm with optional approximation methods.
vector<int> ApproxDadda(map<int, int> Ins, int nIn1, int nIn2, string &file, int approxColumn, int approxMethod)
{
    // approxMethod: 0=exact, 1=truncation only, 2=FA substitution only, 3=both
    assert(approxMethod >= 0 && approxMethod <= 3 && "Approximation method must be 0-3");

    int truncateBits = 0;

    // Apply truncation-based approximation if method includes it (1 or 3)
    if (approxMethod == 1 || approxMethod == 3)
    {
        int maxWeight = 0;
        for (auto const &it : Ins)
        {
            maxWeight = max(maxWeight, it.first);
        }

        // The number of bits to truncate is determined by the maximum weight of the input partial products.
        // The truncation is set to be at least 1 and at most a quarter of the minimum input size, but not exceeding
        // the maximum weight of the inputs.
        if (maxWeight > 0)
        {
            truncateBits = max(1, min(maxWeight, min(nIn1, nIn2) / 4));
        }
    }

    // The approximation is applied only to full-adder reduction nodes in columns [0 .. approxColumn-1].
    // Columns >= approxColumn remain exact, and half-adders stay exact throughout.
    return DaddaCore(Ins, nIn1, nIn2, file, "ADT", truncateBits, approxColumn);
}

// Sayak: The following function implements the Dadda multiplier algorithm without any approximation methods.
vector<int> Dadda(map<int, int> Ins, int nIn1, int nIn2, string &file) // Get two integer numbers as input sizes and create the Wallace Tree PPA
{
    return DaddaCore(Ins, nIn1, nIn2, file, "DT", 0, -1);
}
