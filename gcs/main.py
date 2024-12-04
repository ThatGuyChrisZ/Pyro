import struct
import zlib
import sys
import serial
from packet_class._v2.packet import Packet
PACKET_SIZE = 57 # ADJUST?

def receive_and_decode_packets():
    # Open the serial port connected to the RF module
    try:
        rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=9600, timeout=1) #ADJUST PORT, BAUDRATE AS NECESSARY
        print("Listening for packets on /dev/ttyUSB1...")
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return

    while True:
        try:
            # Read the serialized data from the RF module
            data = rf_serial.read(PACKET_SIZE)

            if len(data) < PACKET_SIZE:
                print("Incomplete packet received, skipping...")
                continue

            # Unpack the payload and checksum
            payload = data[:-4]  # setting to all but the sum . . . 
            received_checksum = struct.unpack('<I', data[-4:])[0] # and here we check that sum

            computed_checksum = zlib.crc32(payload)

            if computed_checksum != received_checksum:
                print(f"Checksum mismatch! Packet corrupted. \\\\ COMPUTED:{computed_checksum}, RECIEVED: {received_checksum}")
                continue

            # DESERIALIZE THE PAYLOAD, PUT BACK INTO A PACKET
            pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', payload)

            packet = Packet(
                pac_id=pac_id,
                gps_data=[lat, lon],
                alt=alt,
                high_temp=high_temp,
                low_temp=low_temp
            )

            # Print the decoded packet
            print(packet)

        except struct.error as e:
            print(f"Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")

if __name__ == '__main__':
    receive_and_decode_packets()