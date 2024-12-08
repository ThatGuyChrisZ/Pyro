# rpt -> Radio protocol test script
# Running into issue where the GCS is only receiving 6-12 bytes of the data packets
# This script is used to help aleviate this issue

import sys
from radio.packet_class._v2.packet import Packet
import struct
import time
import serial

# Configuration
DRONE_SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600
SEND_INTERVAL = 2  # Send every 1 second

# Initialize serial communication
drone_serial = serial.Serial(port=DRONE_SERIAL_PORT, baudrate=BAUD_RATE, timeout=2)

def calculate_checksum(data: bytes) -> int:
    """Calculate checksum by summing bytes and taking modulo 256."""
    return sum(data) % 256

def send_float(value: float):
    """Serialize a float and send it with a checksum."""
    # Serialize the float
    serialized_data = struct.pack('<f', value)  # Little-endian float
    checksum = calculate_checksum(serialized_data)
    
    # Append the checksum
    packet = serialized_data + struct.pack('<B', checksum)
    
    # Send the packet
    drone_serial.write(packet)
    print(f"Sent: {packet.hex()} (float: {value})")

if __name__ == "__main__":
    print("Drone Test Script: Sending serialized float data...")
    try:
        while True:
            test_value = 42.42  # Example float value
            send_float(test_value)
            time.sleep(SEND_INTERVAL)
    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        drone_serial.close()
