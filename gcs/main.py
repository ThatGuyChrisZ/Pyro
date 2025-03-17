###########################################################################
#                                                                         #
#            Contributed by Robb Northrup, Ashton Westenburg              #
#                                                                         #
###########################################################################

prog_mode = 2
          # 0: normal runtime
          # 1: debug mode
          # 2: debug on current system
          #      1.) Intended to have this run on a developer system, on the ride-along board
          #      2.) Data intended to be sent over RF is sent through interprocess communication
          #          means for debugging purposes

import struct
import zlib
import serial
import socket # For UDP socket transmission in MODE 2
import requests
import argparse
import multiprocessing as mp
from packet_class._v4.packet import Packet
import time
import os
import csv
import numpy

# ------------------ #
# NETWORK MANAGEMENT #
# ------------------ #
PACKET_SIZE = 32  # ADJUST?
REQ_PACKET_SIZE = (3 + 4) # String (of three letters) + integer size
DRONE_ADDRESS = ("127.0.0.1", 5004)  # Localhost UDP port for drone in mode 2
UDP_PORT = 5005 # Port for UDP communication in debug mode (2)
rf_serial = None

# --------------- #
# LOGS MANAGEMENT #
# --------------- #
LOG_DIR = "trans_logs"  # Folder to store logs of packet transmissions
os.makedirs(LOG_DIR, exist_ok=True)



########################################################################
#   Function Name: receive_and_decode_packets()                        #
#   Author: Ashton Westenburg                                          #
#   Parameters:                                                        #                               
#   Description:                                                       #
#   Return:                                                            #
########################################################################
def send_packet_to_server(q_unser_packets):
    """Sends the decoded packet to the server."""
    if prog_mode != 0:
        print(f"SP: STARTING PROCESS")

    server_url = "http://localhost:8000/add_packet"  # Current Server Location

    while True:
        if not q_unser_packets.empty():
            try:
                packet = q_unser_packets.get()

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
        else:
            pass



########################################################################
#   Function Name: log_radio_logger()                                  #
#   Author: Robb Northrup                                              #
#   Parameters:  q_radio_log                                           #
#   Description: This is is the function/process used to log radio     #
#                transmissions for debugging and performance eval.     #
#   Return: None                                                       #
########################################################################
def get_flight_log_filename():
    """Generate a unique filename for each flight log based on timestamp."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return os.path.join(LOG_DIR, f"{timestamp}.csv")

def setup_csv_logger(csv_file):
    """Ensure CSV file has headers."""
    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "packet_id", "pac_type", "send(s)/receive(r)", "trans_type", "num_transmissions"])  # Define CSV headers

def radio_log_listener(log_queue, csv_file):
    """Process that listens for logs and writes them to CSV."""

    if prog_mode != 0:
        print(f"LL: STARTING PROCESS")

    setup_csv_logger(csv_file)
    
    with open(csv_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        
        while True:
            try:
                record = log_queue.get()
                if record is None:
                    break  # Stop listener when None is received
                
                writer.writerow([record["timestamp"], record["packet_id"], record["pac_type"], record["send(s)/receive(r)"], record["trans_type"], record["num_transmissions"]])
                file.flush()  # Flush immediately to prevent data loss
            
            except Exception as e:
                print("Logging error:", e)

def log_trans_gcs(pac_id, pac_type, send_or_recieve, num_transmissions, q_log):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # --- #
    # LOG #
    # --- #
    # Could be fixed for differenting between timestamps for sent ACKs and received DATs
    trans_type = None
    if prog_mode != 2:
        trans_type = 'RF'
    else:
        trans_type = 'UDP'
    q_log.put({"timestamp": timestamp, "packet_id": pac_id, "send(s)/receive(r)": send_or_recieve, "pac_type": pac_type, "trans_type": trans_type,  "num_transmissions": num_transmissions})



########################################################################
#   Function Name: receive_and_decode_packets()                        #
#   Author: Robb Northrup                                              #
#   Parameters: N/A                                                    #                               
#   Description: Take packets off of the bus, deserialize,             #      
#                and send the packets to send_packet_to_server()       #                                                              #
#   Return: None                                                       #
########################################################################
def receive_and_decode_packets(prog_mode, rf_serial_usb_port, q_unser_packets, q_log):
    if prog_mode != 0:
        print(f"RD: STARTING PROCESS")

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
        
    # Dictionary for logging packet transmissions
    data_pacs_received = {} # House the number of times a packet has been received
        
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

            # Decode Packet info for debugging modes
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
                print(f"RD: Checksum mismatch! Packet corrupted. \\ COMPUTED:{computed_checksum}, RECEIVED: {received_checksum}")
                continue

            # DESERIALIZE THE PAYLOAD, PUT BACK INTO A PACKET
            dat_pac_id, dat_lat, dat_lon, dat_alt, dat_high_temp, dat_low_temp, dat_time_stamp = struct.unpack('<IffIhhq', payload)

            dat_packet = Packet(
                pac_id=dat_pac_id,
                gps_data=[dat_lat, dat_lon],
                alt=dat_alt,
                high_temp=dat_high_temp,
                low_temp=dat_low_temp,
                time_stamp=dat_time_stamp
            )

            # Print the decoded packet
            if prog_mode != 0:
                print(dat_packet)

            # Has the DAT Packet already been received?
            if dat_pac_id in data_pacs_received:
                data_pacs_received[dat_pac_id] = data_pacs_received[dat_pac_id] + 1
                if prog_mode != 0:
                    print(f"RD: DAT Packet ID {dat_pac_id} already has been received {data_pacs_received.get(dat_pac_id)} times!")
            else:
                q_unser_packets.put(dat_packet)
                data_pacs_received[dat_pac_id] = 1
                if prog_mode != 0:
                    print(f"RD: DAT Packet ID {dat_pac_id} has been received for the first time")

            # Log/Acknowledge Recipient
            if prog_mode != 0:
                print(f"RD: Packet ID {dat_pac_id} unpacked!")
            log_trans_gcs(dat_pac_id, "DAT", "r", data_pacs_received[dat_pac_id], q_log)

            # ---------------- #
            # HANDSHAKE METHOD #
            # ---------------- #
            ack_payload = struct.pack('<3sI', b"ACK", dat_pac_id)
            ack_checksum = zlib.crc32(ack_payload)

            ack_serialized_data = ack_payload + struct.pack('<I', ack_checksum)  # Append checksum as unsigned int
            
            if prog_mode != 2:
                rf_serial.write(ack_serialized_data)
            else:
                udp_socket.sendto(ack_serialized_data, DRONE_ADDRESS)
                print(f"RD: ACK for ID {dat_pac_id} sent to {DRONE_ADDRESS}")
                print(f"RD: ACK packet length: {len(ack_serialized_data)}")

            # Log
            log_trans_gcs(dat_pac_id, "ACK", "s", 1, q_log)

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
    mp.set_start_method('fork')    # 'spawn' : for windows deployment (and safe on linux)
                                    #           + safer for I/O bound and thread-sensitive tasks
                                    #           + safer with multithreading and c-extension libaries
                                    #           + avoids unpredictable behavior of 'fork with shared objects
                                    #             and in the mp.Manager()
                                    #           + fresh, clean process w/o inheriting unnecesary parent resources
                                    #           - slower process than 'fork', new Python interpreter
                                    #           - everything passed to child processes
                                    #           - extra memory usage
                                    #           - worse for CPU-bound processes, slower
                                    # 'fork' : opposite of 'spawn' (see above)
                                    # 'forkserver' : good compromise of 'spawn' and 'fork' (only compatible with unix-based systems)
    # ---------------- #
    # GET PROGRAM MODE #
    # ---------------- #
    prog_mode = 0 # Default mode is normal (not debugging)
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
        # ------------------ #
        # START MAIN PROCESS #
        # ------------------ #
        if prog_mode != 0:
            print(f"Starting Main process, mode {prog_mode}")
        q_unser_packets = mp.Queue()
        q_log = mp.Queue()

        p_rad_log_listener = mp.Process(target=radio_log_listener, args=(q_log, get_flight_log_filename(),))
        p_rec_and_dec = mp.Process(target=receive_and_decode_packets, args=(prog_mode, usb_port_trans, q_unser_packets, q_log,))
        p_send_pac_to_serv = mp.Process(target=send_packet_to_server, args=(q_unser_packets,))

        p_rad_log_listener.start()
        p_rec_and_dec.start()
        p_send_pac_to_serv.start()
