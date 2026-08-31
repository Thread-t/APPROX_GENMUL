#include "GenMul.hpp"

string GenMul(int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum, int approxMethod)
{
    string result = moduleConnector(nIn1, nIn2, firstStage, secondStage, thirdStage, approxColumn, approxCout, approxSum, approxMethod);
    return result;
}

string GenMulNameMaker (int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum, int approxMethod)
{
    string name = nameMaker (nIn1, nIn2, firstStage, secondStage, thirdStage, approxColumn, approxCout, approxSum, approxMethod);
    return name;
}

