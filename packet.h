#include <stdio.h>

class packet {
    public:
        unsigned int pacId;

        packet(unsigned int newPacId); //Only for testing purposes
        packet(unsigned int newPacId, float gpsData[], float alt, float highTemp, float lowTemp);
        packet(unsigned int newPacId, float gpsData[], float alt, float tempData[]);
        int send();
    private:
        bool handshake();
    protected:
};

packet::packet(unsigned int newPacId, float gpsData[], float alt, float highTemp, float lowTemp) {
    pacId = newPacId;
    printf("Created Packet %d\n", pacId);
}

packet::packet(unsigned int newPacId, float gpsData[], float alt, float tempData[]) {
    pacId = newPacId;
    printf("Created Packet %d\n", pacId);
}

packet::packet(unsigned int newPacId) {
    pacId = newPacId;
    printf("Created Packet %d\n", pacId);
}