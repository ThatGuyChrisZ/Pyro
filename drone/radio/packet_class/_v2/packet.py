# ///////////////////////////////////////////////////
# contributed by Robb Northrup
# ///////////////////////////////////////////////////


import struct # For serialization of the data
import zlib # checksum/error detection

class Packet:
    def __init__(self, pac_id, gps_data, alt, high_temp, low_temp):
        self.pac_id = pac_id
        self.gps_data = gps_data # This should be a list of two floats, [lat, long]
        self.alt = alt # Altitude in meters
        self.high_temp = high_temp # Highest temp in cel, of frame
        self.low_temp = low_temp # Lowest temp in cel, of frame

    def serialize(self):
        # The format of the payload is as follows: int, float, float, int, short, short
        payload = struct.pack('<IffIhh', \
            self.pac_id, \
            self.gps_data[0], \
            self.gps_data[1], \
            self.alt, \
            self.high_temp, \
            self.low_temp)
        checksum = zlib.crc32(payload)

        serialized_data = payload + struct.pack('<I', checksum)  # Append checksum as unsigned int

        return serialized_data

    def __str__(self):
        return f"         ======================\n \
             PACKET #{self.pac_id}\n \
        ======================\n \
            PACKET ID - {self.pac_id}\n \
            GPS COORDINATES - {self.gps_data}\n \
            ALTITUDE - {self.alt}\n \
            HIGH TEMP - {self.high_temp}\n \
            LOW TEMP - {self.low_temp}"
