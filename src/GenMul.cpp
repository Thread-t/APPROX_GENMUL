#include "GenMul.hpp"

string GenMul(int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum)
{
    string result = moduleConnector(nIn1, nIn2, firstStage, secondStage, thirdStage, approxColumn, approxCout, approxSum);
    return result;
}

string GenMulNameMaker (int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum)
{
    string name = nameMaker (nIn1, nIn2, firstStage, secondStage, thirdStage, approxColumn, approxCout, approxSum);
    return name;
}

