#include "packet.h"
#include <iostream>
#include <array>
#include <cstring>

// C-style wrapper functions for the Packet class
extern "C" {
    // Constructor wrapper
    Packet* create_packet(unsigned int cPacId, float lat, float lon, float alt, float highTemp, float lowTemp) {
        return new Packet(cPacId, {lat, lon}, alt, highTemp, lowTemp);
    }

    // Serialize wrapper
    void serialize_packet(Packet* packet, unsigned char* buffer) {
        std::array<unsigned char, 20> data = packet->serialize();
        std::memcpy(buffer, data.data(), data.size()); // Copy serialized data into provided buffer
    }

    // Print packet data
    void print_packet(Packet* packet) {
        packet->print();
    }

    // Destructor wrapper
    void destroy_packet(Packet* packet) {
        delete packet;
    }
}