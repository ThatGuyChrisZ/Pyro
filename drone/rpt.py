# ///////////////////////////////////////////////////
# contributed by Robb Northrup
# ///////////////////////////////////////////////////


# rpt -> Radio protocol test script
# Running into issue where the GCS is only receiving 6-12 bytes of the data packets
# This script is used to help aleviate this issue

import sys
from radio.packet_class._v2.packet import Packet
import time
import serial
import struct
import crcmod

# Initialize the serial port
drone_serial = serial.Serial(port="/dev/ttyUSB0", baudrate=57600, timeout=1)

# CRC-8 checksum generator
crc8 = crcmod.predefined.mkCrcFun('crc-8')

def create_packet(data):
    """Create a packet with serialized float and checksum."""
    serialized_data = struct.pack('<f', data)  # Serialize the float (little-endian)
    checksum = crc8(serialized_data)          # Generate checksum
    packet = serialized_data + struct.pack('B', checksum)  # Append checksum
    return packet

if __name__ == "__main__":
    try:
        while True:
            test_value = 42.42  # Example float to send
            packet = create_packet(test_value)
            drone_serial.write(packet)
            drone_serial.flush()  # Ensure all data is sent
            print(f"Sent packet: {packet.hex()}")
            time.sleep(1)  # Send every 1 second
    except KeyboardInterrupt:
        print("Exiting...")
        drone_serial.close()

def alt_test():
    while True:
        drone_serial.write(b"Hello, GCS!\n")
        print("Message sent.")
        time.sleep(1)  # Send a message every second
