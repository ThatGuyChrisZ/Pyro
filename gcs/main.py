###########################################################################
#                                                                         #
#            Contributed by Robb Northrup, Ashton Westenburg              #
#                                                                         #
###########################################################################

import struct
import zlib
import serial
import socket # For UDP socket transmission in MODE 2
import requests
import argparse
from packet_class._v4.packet import Packet

PACKET_SIZE = 32  # ADJUST?
REQ_PACKET_SIZE = (3 + 4) # String (of three letters) + integer size
DRONE_ADDRESS = ("127.0.0.1", 5004)  # Localhost UDP port for drone in mode 2
UDP_PORT = 5005 # Port for UDP communication in debug mode (2)



########################################################################
#   Function Name: receive_and_decode_packets()                        #
#   Author: Ashton Westenburg                                          #
#   Parameters:                                                        #                               
#   Description:                                                       #
#   Return:                                                            #
########################################################################
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
            "time_stamp": packet.time_stamp
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
def receive_and_decode_packets(prog_mode, rf_serial, rf_serial_usb_port):
    # UDP socket debug mode (local)
    if prog_mode == 2:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("127.0.0.1", UDP_PORT))
        print(f"RD: Listening for packets on UDP Port {UDP_PORT}...")

    # Mode 0|1: Read from RF serial
    else:
        try:
            # Open the serial port connected to the RF module
            print(f"RD: Listening for packets on /dev/ttyUSB{rf_serial_usb_port}...")
        except serial.SerialException as e:
            print(f"RD: Error opening serial port: {e}")
            return
        
    # Program loop for receiving, deserializing, sending ACKs, and shipping
    # off packets to the send_packet_to_server() method
    while True:
        try:
            # Receive the data off the bus
            if prog_mode == 2:
                data, addr = udp_socket.recvfrom(PACKET_SIZE)
                print(f"Received packet from {addr}")
            # Read the serialized data from the RF module
            else:
                data = rf_serial.read(PACKET_SIZE)

            if prog_mode != 0:
                print(f"\nPACKET LENGTH: {len(data)}")
                print(f'PACKET RECEIVED: {data.hex()}')  # Print as hex for readability
                if len(data) < PACKET_SIZE:
                    print("Incomplete packet received, skipping...")
                    continue

            # Unpack the payload and checksum
            payload = data[:-4]  # setting to all but the sum . . . 
            received_checksum = struct.unpack('<I', data[-4:])[0] # and here we check that sum

            computed_checksum = zlib.crc32(payload)

            if computed_checksum != received_checksum:
                print(f"Checksum mismatch! Packet corrupted. \\ COMPUTED:{computed_checksum}, RECEIVED: {received_checksum}")
                continue

            # DESERIALIZE THE PAYLOAD, PUT BACK INTO A PACKET
            pac_id, lat, lon, alt, high_temp, low_temp, time_stamp = struct.unpack('<IffIhhq', payload)

            packet = Packet(
                pac_id=pac_id,
                gps_data=[lat, lon],
                alt=alt,
                high_temp=high_temp,
                low_temp=low_temp,
                time_stamp=time_stamp
            )

            # ---------------- #
            # HANDSHAKE METHOD #
            # ---------------- #
            ack_payload = struct.pack('<3sI', b"ACK", packet.pac_id)
            ack_checksum = zlib.crc32(ack_payload)

            ack_serialized_data = ack_payload + struct.pack('<I', ack_checksum)  # Append checksum as unsigned int
            
            if prog_mode != 2:
                rf_serial.write(ack_serialized_data)
            else:
                udp_socket.sendto(ack_serialized_data, DRONE_ADDRESS)
                print(f"RD: ACK for ID {packet.pac_id} sent to {DRONE_ADDRESS}")

            # Print the decoded packet and send to the server
            if prog_mode != 0:
                print(packet)
            send_packet_to_server(packet)
            if prog_mode != 0:
                print(f"RD: sent ACK packet for ID {packet.pac_id}")
            print(f"ACK packet length: {len(ack_serialized_data)}")

        except struct.error as e:
            print(f"RD: Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"RD: Serial communication error: {e}")



########################################################################
#   Function Name: __main__()                                          #
#   Author: Robb Northrup                                              #
#   Parameters:                                                        #                               
#   Description:                                                       #
#   Return: None                                                       #
########################################################################
if __name__ == '__main__':
    prog_mode = 0 # Default mode is normal (not debugging)
    rf_serial = None
    usb_port_trans = None

    parser = argparse.ArgumentParser(description="Provide the mode of the program you wish to run.")
    parser.add_argument("--mode", type=int, help="MODES: 0-Basic | 1-Debug | 2-Local Sys Debug")
    args = parser.parse_args()
    if args.mode is not None:  # Avoid overwriting if mode isn't provided
        prog_mode = args.mode
    if prog_mode != 2:
        usb_port_trans = input("Enter the usb port the tranceiver is plugged into (type /'q/' to exit): ")
    
    if usb_port_trans == 'q':
        quit()
    else:
        receive_and_decode_packets(prog_mode, rf_serial, usb_port_trans)
