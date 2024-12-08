from packet_class._v2.packet import Packet
import serial
import struct
import crcmod

# Initialize the serial port
gcs_serial = serial.Serial(port="/dev/ttyUSB1", baudrate=57600, timeout=1)

# CRC-8 checksum generator
crc8 = crcmod.predefined.mkCrcFun('crc-8')

def validate_and_unpack(packet):
    """Validate packet checksum and deserialize float."""
    serialized_data = packet[:4]   # First 4 bytes for float
    received_checksum = packet[4] # Last byte for checksum

    # Calculate checksum
    calculated_checksum = crc8(serialized_data)
    if calculated_checksum == received_checksum:
        value = struct.unpack('<f', serialized_data)[0]  # Deserialize float
        return value, True
    else:
        return None, False

if __name__ == "__main__":
    try:
        while True:
            packet = gcs_serial.read(5)  # Read 5 bytes (4 for float + 1 for checksum)
            if len(packet) == 5:
                value, is_valid = validate_and_unpack(packet)
                if is_valid:
                    print(f"Received valid packet: {packet.hex()} | Float: {value}")
                else:
                    print(f"Checksum mismatch! Packet: {packet.hex()}")
            else:
                print(f"Incomplete packet received. LENGTH: {len(packet)} | CONTENTS: {packet.hex()}")
    except KeyboardInterrupt:
        print("Exiting...")
        gcs_serial.close()


# Adjust the port and baud rate as needed
ser = serial.Serial('/dev/ttyUSB1', baudrate=57600, timeout=1)
def alt_test():
    while True:
        message = ser.readline()
        if message:
            print(f"Message received: {message.decode('utf-8').strip()}")

