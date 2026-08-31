#include "GenMul.hpp"

#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {


// Parses a string as an integer. Returns true if the string is a valid integer, false otherwise.
bool parseInteger(const char *text, int &value)
{
    try
    {
        size_t parsedCharacters = 0;
        long long parsedValue = std::stoll(text, &parsedCharacters, 10);

        if (text[parsedCharacters] != '\0' ||
            parsedValue < std::numeric_limits<int>::min() ||
            parsedValue > std::numeric_limits<int>::max())
        {
            return false;
        }

        value = static_cast<int>(parsedValue);
        return true;
    }
    catch (const std::exception &)
    {
        return false;
    }
}

// Parses a command line argument as an integer and checks if it is within the specified range.
bool parseArgument(const char *text, const std::string &name, int minimum, int maximum, int &value)
{
    if (!parseInteger(text, value) || value < minimum || value > maximum)
    {
        std::cerr << "Invalid " << name << ": " << text
                  << " (expected " << minimum << ".." << maximum << ")" << std::endl;
        return false;
    }

    return true;
}

bool readValue(const std::string &prompt, int minimum, int maximum, int &value)
{
    std::cout << prompt;
    if (!(std::cin >> value) || value < minimum || value > maximum)
    {
        std::cerr << "Wrong input (expected " << minimum << ".." << maximum << ")." << std::endl;
        return false;
    }

    return true;
}

void printUsage(const char *program)
{
    std::cerr
        << "Usage:\n"
        << "  " << program << " <ppg> <ppa> <fsa> <in1-bits> <in2-bits>\n"
        << "  " << program << " <ppg> 5 <fsa> <in1-bits> <in2-bits>"
        << " <dadda-column> <carry-mask> <sum-mask> [approx-method]\n\n"
        << "ppg: 1=unsigned, 2=signed\n"
        << "ppa: 1=array, 2=Wallace, 3=Dadda, 4=counter-Wallace, 5=approximate Dadda\n"
        << "fsa: 1=ripple, 2=CLA, 3=Lander-Fischer, 4=Kogge-Stone,"
        << " 5=Brent-Kung, 6=carry-skip, 7=serial-prefix\n"
        << "approx-method: 0=exact, 1=truncation only, 2=FA substitution only, 3=both\n"
        << "carry-mask and sum-mask must be decimal values from 0 to 255.\n";
}

void printBanner()
{
    std::cout << "Compilation time: " << GLOBAL_COMPILATION_TIME << '\n'
              << "Compilation SHA256 message digest: " << GLOBAL_SHA256 << "\n\n"
              << "/-------------------------------------------------------------------------\\\n"
              << "|  Multiplier Generator GenMul                                            |\n"
              << "|                                                                         |\n"
              << "|  Copyright (c) 2019-2020 University of Bremen, Germany.                 |\n"
              << "|  Copyright (c) 2020 Johannes Kepler University Linz, Austria.           |\n"
              << "|                                                                         |\n"
              << "|  You can find GenMul at: http://www.sca-verification.org/genmul         |\n"
              << "|  Contact us at genmul@sca-verification.org                              |\n"
              << "\\-------------------------------------------------------------------------/\n\n";
}

} // namespace

int main(int argc, char **argv)
{
    int firstStage = 1;
    int secondStage = 1;
    int thirdStage = 1;
    int in1Size = 0;
    int in2Size = 0;

    // Ignored unless PPA 5 (approximate Dadda) is selected.
    int approxColumn = 0;
    int approxCout = 23;
    int approxSum = 105;
    int approxMethod = 2;

    if (argc == 1)
    {
        printBanner();

        std::cout << "Partial Product Generator (PPG):\n"
                  << "1. Unsigned PPG\n"
                  << "2. Signed PPG\n";
        if (!readValue(">> ", 1, 2, firstStage))
            return 1;

        std::cout << "\nPartial Product Accumulator (PPA):\n"
                  << "1. Array\n"
                  << "2. Wallace tree\n"
                  << "3. Dadda tree\n"
                  << "4. Counter-based Wallace tree\n"
                  << "5. Approximate Dadda tree\n";
        if (!readValue(">> ", 1, 5, secondStage))
            return 1;

        std::cout << "\nFinal Stage Adder (FSA):\n"
                  << "1. Ripple Carry Adder\n"
                  << "2. Carry Look-Ahead Adder\n"
                  << "3. Lander-Fischer Adder\n"
                  << "4. Kogge-Stone Adder\n"
                  << "5. Brent-Kung Adder\n"
                  << "6. Carry Skip Adder\n"
                  << "7. Serial Prefix Adder\n";
        if (!readValue(">> ", 1, 7, thirdStage))
            return 1;

        if (!readValue("First input size: ", 1, std::numeric_limits<int>::max(), in1Size) ||
            !readValue("Second input size: ", 1, std::numeric_limits<int>::max(), in2Size))
        {
            return 1;
        }

        if (secondStage == 5)
        {
            const int maximumColumn = in1Size + in2Size - 2;
            std::cout << "\nThe selected Dadda column contains only approximate full adders; "
                      << "half adders remain exact.\n";

            if (!readValue("Dadda column to approximate: ", 0, maximumColumn, approxColumn) ||
                !readValue("Carry truth-table mask (0..255): ", 0, 255, approxCout) ||
                !readValue("Sum truth-table mask (0..255): ", 0, 255, approxSum) ||
                !readValue("Approximation method (0=exact,1=truncation,2=FA-sub,3=both): ", 0, 3, approxMethod))
            {
                return 1;
            }
        }
    }
    else
    {
        if (argc != 6 && argc != 9 && argc != 10)
        {
            printUsage(argv[0]);
            return 1;
        }

        // Parse command line arguments.
        if (!parseArgument(argv[1], "PPG", 1, 2, firstStage) ||
            !parseArgument(argv[2], "PPA", 1, 5, secondStage) ||
            !parseArgument(argv[3], "FSA", 1, 7, thirdStage) ||
            !parseArgument(argv[4], "first input size", 1, std::numeric_limits<int>::max(), in1Size) ||
            !parseArgument(argv[5], "second input size", 1, std::numeric_limits<int>::max(), in2Size))
        {
            return 1;
        }

        if (secondStage == 5)
        {
            if (argc != 9 && argc != 10)
            {
                printUsage(argv[0]);
                return 1;
            }

            // Parse additional arguments if it is approximate Dadda.
            const int maximumColumn = in1Size + in2Size - 2;
            if (!parseArgument(argv[6], "Dadda column", 0, maximumColumn, approxColumn) ||
                !parseArgument(argv[7], "carry mask", 0, 255, approxCout) ||
                !parseArgument(argv[8], "sum mask", 0, 255, approxSum))
            {
                return 1;
            }

            if (argc == 10 && !parseArgument(argv[9], "approximation method", 0, 3, approxMethod))
            {
                return 1;
            }
        }
        // If it is not approximate Dadda, there should be no additional arguments.
        else if (argc != 6)
        {
            printUsage(argv[0]);
            return 1;
        }
    }

    const std::string name = GenMulNameMaker(
        in1Size, in2Size, firstStage, secondStage, thirdStage,
        approxColumn, approxCout, approxSum, approxMethod);
    const std::string finalCode = GenMul(
        in1Size, in2Size, firstStage, secondStage, thirdStage,
        approxColumn, approxCout, approxSum, approxMethod);

    std::ofstream file(name);
    if (!file)
    {
        std::cerr << "Could not open output file: " << name << std::endl;
        return 1;
    }

    file << finalCode;
    if (!file)
    {
        std::cerr << "Could not write output file: " << name << std::endl;
        return 1;
    }

    std::cout << "*************************************************************************\n"
              << "Output file: " << name << std::endl;
    return 0;
}
