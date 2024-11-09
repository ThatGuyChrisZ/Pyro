#include <iostream>
#include <vector>
#include <array>

class Packet {
    public:
        // packet(unsigned int newPacId); //Only for testing purposes
        // packet(unsigned int newPacId, float gpsData[], float alt, float tempData[]);
        Packet(unsigned int cPacId, std::array<float, 2> cGpsData, float cAlt, float cHighTemp, float cLowTemp)
            : pacId(cPacId), gpsData(cGpsData), alt(cAlt), highTemp(cHighTemp), lowTemp(cLowTemp) {};
        int send();

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

        bool handshake();
};

void Packet::print() const {
    std::cout << "Packet ID: " << pacId << "\n";
    std::cout << "GPS: (" << gpsData[0] << ", " << gpsData[1] << ")\n";
    std::cout << "Altitude: " << alt << "\n";
    std::cout << "High temp: " << highTemp << "\n";
    std::cout << "Low temp: " << lowTemp << "\n";
}