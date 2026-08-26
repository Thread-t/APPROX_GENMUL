#include "Dadda.hpp"
#include "ApproxConfig.hpp"

#define UNUSED(x) (void)(x)

static vector<int> DaddaCore(map<int, int> Ins, int nIn1, int nIn2, string &file, const string &typeName, int truncateBits)
{
    UNUSED(nIn1);
    UNUSED(nIn2);

    int inputNumber = 0;
    vector<PartialProduct> partialIn;
    for (auto i = 0u; i < Ins.size(); i++)
    {
        for (int j = 0; j < Ins[i]; j++)
        {
            PartialProduct p(i);
            partialIn.push_back(p);
            inputNumber++;
        }
    }

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

    vector<PartialProduct> partialOut;
    vector<Component *> compList;

    map<int, vector<PartialProduct>> LevelizedPartials;
    PartialProduct::LevelizePartials(LevelizedPartials, partialIn);

    Component *comp;

    unsigned int maxh = 0;
    for (auto i: LevelizedPartials)
    {
        if (i.second.size()>maxh)
            maxh = i.second.size();
    }

    int d = 2;
    vector<int> D = {d};

    bool stopFlag = false;

    while (!stopFlag)
    {
        d = 1.5 * d;
        D.push_back(d);
        if ((1.5 * d) > maxh)
            stopFlag = true;
    }
    reverse(D.begin(), D.end());

    map<int, int> height;

    for (auto i : LevelizedPartials)
    {
        height[i.first] = i.second.size();
    }

    vector<PartialProduct> GeneratedAtLevel;
    for (auto n = 0u; n < D.size(); n++)
    {
        for (auto i = 0u; i < LevelizedPartials.size(); i++)
        {
            while (1)
            {
                if (height[i] <= D[n])
                {
                    break;
                }
                else if (height[i] == D[n] + 1)
                {
                    height[i]--;
                    height[i + 1]++;
                    comp = new HalfAdder({LevelizedPartials[i][0], LevelizedPartials[i][1]});
                    comp->SetOutputs();
                    LevelizedPartials[i].erase(LevelizedPartials[i].begin(), LevelizedPartials[i].begin() + 2);
                    compList.push_back(comp);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[0]);
                    GeneratedAtLevel.push_back(comp->returnOutputs()[1]);
                    break;
                }
                else
                {
                    height[i] -= 2;
                    height[i + 1]++;
                    // Sayak: Use approximate full-adder if available for the given weight
                    comp = new FullAdder({LevelizedPartials[i][0], LevelizedPartials[i][1], LevelizedPartials[i][2]});
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
    }

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

    vector<PartialProduct> OutPar1;
    vector<PartialProduct> OutPar2;
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

    for (auto i = 0u; i < LevelizedPartials.size(); i++)
    {
        if (LevelizedPartials[i].size() == 1)
            singleBitNumber++;
        else
            break;
    }

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

    GenerateHeader(Ins.size(), typeName, file);
    GenereateInOutSig(Ins, nOut1, nOut2, file);
    vector<int> signalIDs = Component::collectIDs(compList);
    map<int, string> wireHash = generateWires(Ins, signalIDs, OutPar1, OutPar2, file);
    GenerateComponents(wireHash, compList, file);
    file += "endmodule\n";
    return {(int)OutPar1.size(), (int)OutPar2.size(), singleBitNumber};
}

vector<int> ApproxDadda(map<int, int> Ins, int nIn1, int nIn2, string &file, int approxMethod)
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

        // The number of bits to truncate is determined by
        // the maximum weight of the input partial products.
        // The truncation is set to be at least 1 and at most
        // a quarter of the minimum input size, but not exceeding
        // the maximum weight of the inputs.
        if (maxWeight > 0)
        {
            truncateBits = max(1, min(maxWeight, min(nIn1, nIn2) / 4));
        }
    }

    // map<int, int> approxIns;
    // // The input partial products are adjusted based on the truncation.
    // for (auto const &it : Ins)
    // {
    //     if (truncateBits > 0 && it.first < truncateBits)
    //     {
    //         continue;
    //     }
    //     int adjustedWeight = (truncateBits > 0) ? (it.first - truncateBits) : it.first;
    //     approxIns[adjustedWeight] += it.second;
    // }

    // if (approxIns.empty())
    // {
    //     approxIns[0] = 1;
    // }
    return DaddaCore(Ins, nIn1, nIn2, file, "ADT", truncateBits);
}

vector<int> Dadda(map<int, int> Ins, int nIn1, int nIn2, string &file) // Get two integer numbers as input sizes and create the Wallace Tree PPA
{
    return DaddaCore(Ins, nIn1, nIn2, file, "DT", 0);
}
