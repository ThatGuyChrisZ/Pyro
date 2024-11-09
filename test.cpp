#include <iostream>
#include <vector>
#include "packet.h"

bool test1();

int main() {
    Packet myPacket();

    test1();

    return 0;
}

bool test1() {
    unsigned int myId = 1111;
    float myAlt = 4.5689f;
    std::array<float, 2> myGpsData = {3.12345f, 7.123453f};
    float myHighTemp = 302.5f;
    float myLowTemp = 12.3f;

    Packet myPacket(myId, myGpsData, myAlt, myHighTemp, myLowTemp);
    
    myPacket.print();
}