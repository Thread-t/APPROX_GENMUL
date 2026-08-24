#include "GenMul.hpp"
#include <fstream>


//TODO: Adding later command line features
//#pragma GCC diagnostic ignored "-Wunused-parameter"
int main(int argc, char **argv)
{
    string firstStageString, secondStageString, thirdStageString;
    int firstStage = 1, secondStage = 1, thirdStage = 1, approxErrorLevel = 1, approxMethod = 3;

    int in1Size = 0, in2Size = 0;
    string fileAddress;

    bool cmdline = false;
    if (argc >= 6) {
        firstStage = stoi(argv[1]);
        secondStage = stoi(argv[2]);
        thirdStage = stoi(argv[3]);
        in1Size = stoi(argv[4]);
        in2Size = stoi(argv[5]);
        //sayak: If the second stage is Approximate Dadda tree, 
        //then we can optionally specify the approximation 
        // error level as the 6th argument.
        if (argc >= 7) {
            if (secondStage == 5) {
                approxErrorLevel = stoi(argv[6]);
            }
        }
        if (argc >= 8) {
            if (secondStage == 5) {
                approxMethod = stoi(argv[7]);
            }
        }
        cmdline = true;
    }
    else if (argc==2) {
      if (std::string(argv[1]) == "A")  {
	  in1Size = 10; in2Size = 10; fileAddress = "test-out-A.v"; firstStage = 1; secondStage = 1; thirdStage = 1;
	  cmdline = true;
	  cout << "Running in cmd line mode "<<endl;
      }
    }

  if (cmdline == false ) {
    cout<<"Compilation time: "<<GLOBAL_COMPILATION_TIME<<endl;
    cout<<"Compilation SHA256 message digest: "<<GLOBAL_SHA256<<endl<<endl;
    cout<<"/-------------------------------------------------------------------------\\"<<endl;
    cout<<"|  Multiplier Generator GenMul                                            |"<<endl;
    cout<<"|                                                                         |"<<endl;
    cout<<"|  Copyright (c) 2019-2020 University of Bremen, Germany.                 |"<<endl;
    cout<<"|  Copyright (c) 2020 Johannes Kepler University Linz, Austria.           |"<<endl;
    cout<<"|                                                                         |"<<endl;
    cout<<"|  You can find GenMul at: http://www.sca-verification.org/genmul         |"<<endl;
    cout<<"|  Contact us at genmul@sca-verification.org                              |"<<endl;
    cout<<"\\-------------------------------------------------------------------------/"<<endl;
    cout<<endl;
    cout<<"Enter the number indicating Partial Product Generator (PPG) architecture: "<<endl;
    cout<<"1. Unsigned PPG"<<endl;
    cout<<"2. Signed PPG"<<endl;
    cout<<">> ";
    cin>>firstStageString;
    cout<<"*************************************************************************"<<endl<<flush;
    if (firstStageString!="1" && firstStageString!="2")
    {
        cout<<"Wrong input!!!"<<endl;
        return 0;
    }
    firstStage = stoi(firstStageString);

    cout<<"Enter the number indicating Partial Product Accumulator (PPA) architecture: "<<endl;
    cout<<"1. Array"<<endl;
    cout<<"2. Wallace tree"<<endl;
    cout<<"3. Dadda tree"<<endl;
    cout<<"4. Counter-based Wallace tree"<<endl;
    cout<<"5. Approximate Dadda tree (FV-LIDAC style)"<<endl;
    cout<<">> ";
    cin>>secondStageString;
    cout<<"*************************************************************************"<<endl;
    if (secondStageString!="1" && secondStageString!="2" && secondStageString!="3" && secondStageString!="4" && secondStageString!="5")
    {
        cout<<"Wrong input!!!"<<endl;
        return 0;
    }
    secondStage = stoi(secondStageString);

    //sayak: If the second stage is Approximate Dadda tree, 
    // then we can optionally specify the approximation error level.
    if (secondStage == 5)
    {
        cout << "Approximation error level for FV-LIDAC-style FA:" << endl;
        cout << "0. Exact" << endl;
        cout << "1. Low" << endl;
        cout << "2. Medium" << endl;
        cout << "3. High" << endl;
        cout << ">> ";
        cin >> approxErrorLevel;
        if (cin.fail() || approxErrorLevel < 0 || approxErrorLevel > 3)
        {
            cout << "Wrong input!!!" << endl;
            return 0;
        }
    }

    //
    if (secondStage == 5)
    {
        cout << "Approximation method for FV-LIDAC-style ADT:" << endl;
        cout << "0. Exact (no approximation)" << endl;
        cout << "1. Truncation only" << endl;
        cout << "2. FA-substitution only" << endl;
        cout << "3. Both (truncation + FA-substitution)" << endl;
        cout << ">> ";
        cin >> approxMethod;
        if (cin.fail() || approxMethod < 0 || approxMethod > 3)
        {
            cout << "Wrong input!!!" << endl;
            return 0;
        }
    }

    cout<<"Enter the number indicating Final Stage Adder (FSA) architecture: "<<endl;
    cout<<"1. Ripple Carry Adder"<<endl;
    cout<<"2. Carry Look-Ahead Adder"<<endl;
    cout<<"3. Lander-Fischer Adder"<<endl;
    cout<<"4. Kogge-Stone Adder"<<endl;
    cout<<"5. Brent-Kung Adder"<<endl;
    cout<<"6. Carry Skip Adder"<<endl;
    cout<<"7. Serial Prefix Adder"<<endl;
    cout<<">> ";
    cin>>thirdStageString;
    cout<<"*************************************************************************"<<endl;
    if (thirdStageString!="1" && thirdStageString!="2" && thirdStageString!="3" && thirdStageString!="4" && thirdStageString!="5" && thirdStageString!="6" && thirdStageString!="7")
    {
        cout<<"Wrong input!!!"<<endl;
        return 0;
    }
    thirdStage = stoi(thirdStageString);

    //int in1Size, in2Size;
    cout<<"First input size: ";
    cin >> in1Size;
    if (cin.fail() || in1Size<=0)
    {
        cout<<"Wrong input!!!"<<endl;
        return 0;
    }

    cout<<"Second input size: ";
    cin >> in2Size;
    if (cin.fail() || in2Size<=0)
    {
        cout<<"Wrong input!!!"<<endl;
        return 0;
    }
    //cout<<"*************************************************************************"<<endl;
    //string fileAddress = "Multiplier.v";
    //cout<<"Output file: ";
    //cin >> fileAddress;

  } // end of cmdline == false

    string name = GenMulNameMaker(in1Size, in2Size, firstStage, secondStage, thirdStage, approxErrorLevel, approxMethod);
    cout<<"*************************************************************************"<<endl;
    cout<<"Output file: "<<name<<endl;

    string finalCode = GenMul(in1Size, in2Size, firstStage, secondStage, thirdStage, approxErrorLevel, approxMethod);

    ofstream file;
    file.open(name);

    file << finalCode;

    //moduleConnector(10, 5, "10bit-SPS-WL-CK.v");
    //ofstream file("48bit.v");
    //CarrySkipAdderVariable(48, 48, file);
}
