import struct
import zlib
import sys
import serial
import json
import requests
from packet_class._v2.packet import Packet

PACKET_SIZE = 24  # ADJUST?

# Possible function to forward packets to server alongside Robb's current implementation in receive_and_decode_packets
def send_packet_to_server(packet):
    """Sends the decoded packet to the server."""
    server_url = "http://localhost:8000/add_packet"  # Current Server Location
    try:
        packet_data = {
            "pac_id": packet.pac_id,
            "gps_data": packet.gps_data,
            "alt": packet.alt,
            "high_temp": packet.high_temp,
            "low_temp": packet.low_temp,
        }

        response = requests.post(server_url, json=packet_data)
        if response.status_code == 200:
            print("Packet successfully sent to server.")
        else:
            print(f"Failed to send packet to server. Status code: {response.status_code}, Response: {response.text}")
    except requests.RequestException as e:
        print(f"Error connecting to the server: {e}")

def receive_and_decode_packets():
    # Open the serial port connected to the RF module
    try:
        rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
        print("Listening for packets on /dev/ttyUSB1...")
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return

    while True:
        try:
            # Read the serialized data from the RF module
            data = rf_serial.read(PACKET_SIZE)

            print(f"\nPACKET LENGTH: {len(data)}")
            print(f'PACKET RECIEVED: {data.hex()}')  # Print as hex for readability
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

            # Print the decoded packet and send to the server
            print(packet)
            send_packet_to_server(packet)

        except struct.error as e:
            print(f"Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")

if __name__ == '__main__':
    receive_and_decode_packets()