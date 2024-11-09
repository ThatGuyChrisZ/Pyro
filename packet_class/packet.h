#include <iostream>
#include <array>
#include <cstring> //LIB FOR MEMCOPY

class Packet {
    public:
        // packet(unsigned int newPacId); //Only for testing purposes
        // packet(unsigned int newPacId, float gpsData[], float alt, float tempData[]);
        Packet(unsigned int cPacId, std::array<float, 2> cGpsData, float cAlt, float cHighTemp, float cLowTemp)
            : pacId(cPacId), gpsData(cGpsData), alt(cAlt), highTemp(cHighTemp), lowTemp(cLowTemp) {};

        std::array<unsigned char, 20> serialize() const;
        bool send_to_packet_manager(); //Don't know if I need to implement, will probably be done in the main file

        // GETTERS
        unsigned int get_id() {return pacId;}
        std::array<float, 2> get_gps_data() {return gpsData;}
        float get_alt() const {return alt;}
        float get_high_temp() const {return highTemp;}
        float get_low_temp() const {return lowTemp;};
        void print() const; // Print, getter

    private:
        const unsigned int pacId;
        std::array<float, 2> gpsData; // Fixed-size array for latitude and longitude
        float alt;
        float highTemp;
        float lowTemp;
};

// bool Packet::send_to_packet_manager() {
//     std::array<unsigned char, 20> serializedData = serialize();

//     // SEND TO PACKET MANAGER
// }

std::array<unsigned char, 20> Packet::serialize() const {
    std::array<unsigned char, 20> buffer{};

    // Copy data into buffer (assuming each float is 4 bytes and unsigned int is 4 bytes)
    std::memcpy(&buffer[0], &pacId, sizeof(pacId));
    std::memcpy(&buffer[4], &gpsData[0], sizeof(gpsData[0]));
    std::memcpy(&buffer[8], &gpsData[1], sizeof(gpsData[1]));
    std::memcpy(&buffer[12], &alt, sizeof(alt));
    std::memcpy(&buffer[16], &highTemp, sizeof(highTemp));
    std::memcpy(&buffer[20], &lowTemp, sizeof(lowTemp));

    return buffer;
}

void Packet::print() const {
    std::cout << "Packet ID: " << pacId << "\n";
    std::cout << "GPS: (" << gpsData[0] << ", " << gpsData[1] << ")\n";
    std::cout << "Altitude: " << alt << "\n";
    std::cout << "High temp: " << highTemp << "\n";
    std::cout << "Low temp: " << lowTemp << "\n";
}