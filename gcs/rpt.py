from packet_class._v2.packet import Packet

import struct
import serial

# Configuration
GCS_SERIAL_PORT = '/dev/ttyUSB1'  # Replace with appropriate port
BAUD_RATE = 9600

# Initialize serial communication
gcs_serial = serial.Serial(port=GCS_SERIAL_PORT, baudrate=BAUD_RATE, timeout=2)

def calculate_checksum(data: bytes) -> int:
    """Calculate checksum by summing bytes and taking modulo 256."""
    return sum(data) % 256

def receive_and_validate():
    """Accumulate data until a full packet is received."""
    packet = gcs_serial.read(5)  # Try to read 5 bytes
    while len(packet) < 5:
        packet += gcs_serial.read(5 - len(packet))  # Read missing bytes
    
    if len(packet) == 5:
        serialized_data, received_checksum = packet[:4], packet[4]
        calculated_checksum = calculate_checksum(serialized_data)
        
        if calculated_checksum == received_checksum:
            value = struct.unpack('<f', serialized_data)[0]  # Deserialize float
            print(f"Received: {packet.hex()} (float: {value}, checksum: valid)")
        else:
            print(f"Checksum mismatch! Received: {packet.hex()} (calculated: {calculated_checksum}, received: {received_checksum})")
    else:
        print(f"Incomplete packet received. LENGTH: {len(packet)} | CONTENTS: {packet.hex()}")


if __name__ == "__main__":
    print("GCS Test Script: Receiving and validating serialized float data...")
    try:
        while True:
            receive_and_validate()
    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        gcs_serial.close()
