#include "ModuleConnector.hpp"

//Sayak: Fall back to the default multiplier generation function if no approximation is specified.
string GenMul(int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum, int approxMethod = 2); // create Multiplier
string GenMulNameMaker (int nIn1, int nIn2, int firstStage, int secondStage, int thirdStage, int approxColumn, int approxCout, int approxSum, int approxMethod = 2);  //create Multiplier name
