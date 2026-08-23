#include "GenMul.hpp"

string GenMul(int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxErrorLevel)
{
    string result = moduleConnector(nIn1, nIn2, firstStage, secondStage, thirdStage, approxErrorLevel);
    return result;
}

string GenMulNameMaker (int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxErrorLevel) 
{
    string name = nameMaker (nIn1, nIn2, firstStage, secondStage, thirdStage, approxErrorLevel);
    return name;
}


