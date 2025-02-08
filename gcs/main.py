import struct
import zlib
import sys
import serial
import socket # For UDP socket transmission in MODE 2
import json
import requests
from packet_class._v2.packet import Packet

PACKET_SIZE = 24  # ADJUST?
ACK_PACKET_SIZE = (3 + 8) # String (of three letters) + integer size
UDP_PORT = 5005 # Port for UDP communication in debug mode (2)

prog_mode = 2 # Change this to run in a different mode

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



########################################################################
#   Function Name: receive_and_decode_packets()                        #
#   Author: Robb Northrup                                              #
#   Parameters: N/A                                                    #                               
#   Description: Take packets off of the bus, deserialize,             #      
#                and send the packets to send_packet_to_server()       #                                                              #
#   Return: None                                                       #
########################################################################
def receive_and_decode_packets():
    if prog_mode == 2:
        # UDP socket debug mode (local)
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DRGRAM)
        udp_socket.bind(("127.0.0.1", UDP_PORT))
        print(f"Listening for packets on UDP Port {UDP_PORT}...")
    else: # Mode 0|1: Read from RF serial
        # Open the serial port connected to the RF module
        try:
            rf_serial = serial.Serial(port='/dev/ttyUSB0', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
            print("Listening for packets on /dev/ttyUSB0...")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            return

    while True:
        try:
            # Receive the data off the bus
            if prog_mode == 2:
                data, addr = udp_socket.recvfrom(PACKET_SIZE)
                print(f"Received packet from {addr}")
            else:
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

            # Handshake Method
            ACK = struct.pack('<sI', \
                "ACK", \
                packet.pac_id)
            rf_serial.write(ACK)

            # Print the decoded packet and send to the server
            print(packet)
            send_packet_to_server(packet)

        except struct.error as e:
            print(f"Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")

if __name__ == '__main__':
    receive_and_decode_packets()