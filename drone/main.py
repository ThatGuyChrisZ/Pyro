###########################################################################
#                                                                         #
#              Contributed by Chris Zinser, Robb Northrup                 #
#                                                                         #
###########################################################################

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

prog_mode = 2
          # 0: normal runtime
          # 1: debug mode
          # 2: debug on current system
          #      1.) Intended to have this run on a developer system, on the ride-along board
          #      2.) Data intended to be sent over RF is sent through interprocess communication
          #          means for debugging purposes

# --------------- #
# IMPORT PACKAGES #
# --------------- #
import time
# import sys
import argparse
import board
import busio
import adafruit_mlx90640
import multiprocessing as mp
import multiprocessing.managers
import serial # for serial communication over usb
import socket # for debug mode, sending data over a UDP socket meant to emulate RF transmission
import struct
import zlib
import os
import random
import csv
from thermal_data import thermal_data
from radio.packet_class._v4.packet import Packet, Packet_Info, Packet_Info_Dict
import logging
import logging.handlers
import datetime

# ----------------- #
# PAC-ID MANAGEMENT #
# ----------------- #
pac_id_to_create = 1 # Global variable for creating the next packet id (don't kill me)
UNSIGNED_INT_MAX = 2147483647

# ------------------ #
# NETWORK MANAGEMENT #
# ------------------ #
# rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
# alt_sim_file = open('alt_gps.txt', 'r')
# packet_lib = ctypes.CDLL('./packet_class/packet.so')
ACK_PACKET_SIZE = 11 # String (of three letters) [3] + integer size (pac_id) [4] + checksum [4]
GCS_ADDRESS = ("127.0.0.1", 5005)  # Localhost UDP port
gps_sim_file = open('sim_gps.txt', 'r')
UDP_PORT = 5004
CALL_SIGN = "KK72PA"
RF_TRANCIEVER_PORT = '/dev/ttyUSB1'
rf_serial = None

# ----------------------- #
# THERMAL CAMERA SETTINGS #
# ----------------------- #
PRINT_TEMPERATURES = True
PRINT_ASCIIART = False

# --------------- #
# LOGS MANAGEMENT #
# --------------- #
LOG_DIR = "trans_logs"  # Folder to store logs of packet transmissions
os.makedirs(LOG_DIR, exist_ok=True)



########################################################################
#   Function Name: gps_sim                                             #
#   Author: Chris Zinser                                               #
#   Paramters: queue                                                   #
#   Description: This function reads data out of the gps sim file      #
#                and places it into a queue for the                    #
#                 data_structure_builder process. This allows us to    # 
#                  test the gps system without a physical flight.      #
#   Return: None                                                       #
########################################################################
def gps_sim(q5):
    #Pulls simulated gps data from sim file
    for pair in gps_sim_file:
        q5.put(pair)
        time.sleep(0.2)



########################################################################
#   Function Name: data_structure_builder                              #
#   Author: Chris Zinser                                               #
#   Parameters: queue <int> , queue <thermal_data>                     #
#               ,queue <(float,float)>                                 #
#   Description: This function recieves frames from the main thread    #
#                via a shared queue and place the frame in a           #
#                data structure along with gps and altitude data       #       
#   Return: None                                                       #
########################################################################
def data_structure_builder(q1,q2,q5):
    #Initialize variables and set to resting values
    thermal = ()
    output = (39.5389603,-119.811504)
    #loop check for if a frame is available to process
    pid = os.getpid()
    os.sched_setaffinity(pid, {1})
    while True:
        #print("Data Structure Builder running on core:",os.sched_getaffinity(pid)  )
        if q5.empty() == False:
            #retrieve gps data
            output = q5.get()
            output = str(output).split(",")
            
        if q1.empty() == False:
            #process frame
            
            #print("GO")
            
            #Set data structures gps and barometric values
            thermal = thermal_data(q1.get())
            thermal.gps = (float(output[0]),float(output[1]))
            
            thermal.barometric = 400
            thermal.time_stamp = time.time_ns()
            q2.put(thermal)
            
            #print("Output")
            #print(output)         
            
        

########################################################################
#   Function Name: data_processing                                     #
#   Author: Chris Zinser                                               #
#   Parameters: queue <thermal_data> , queue <thermal_data>            #                               
#   Description: This function recieves frames from the                #
#                data_structure_builder process and applies            #
#                modification as needed                                #                            
#   Return: None                                                       #
########################################################################
def data_processing(q2,q3):
    pid = os.getpid()
    os.sched_setaffinity(pid, {2})
    # pulls thermal data as available by queue
    while True:
        if q2.empty() == False:
            #print("Data processing running on core:",os.sched_getaffinity(pid)  )
            #pushes data to packet creation
            q3.put(q2.get())



########################################################################
#   Function Name: create_packet                                       #
#   Author: Robb Northrup                                              #
#   Parameters: queue <thermal_data> (from data_processing()),         #
#               queue <thermal_data> (to send_packet())                #                               
#   Description: Compartmentalize data in packet, serialize,           #
#                and then send the packet                              #                            
#   Return: None                                                       #
########################################################################
def create_packet(q3, q4):
    global pac_id_to_create
    newest = 0
    pid = os.getpid()
    os.sched_setaffinity(pid, {3})
    while True: 
        if not q3.empty():
            # Get data from the queue
            data = q3.get()

            # Create a Packet object
            packet = Packet(
                pac_id=pac_id_to_create,       # Pulled from global variable
                gps_data=data.gps,             # GPS coordinates [latitude, longitude]
                alt=data.barometric,           # Altitude in meters
                high_temp=data.max_temp,       # Max temperature
                low_temp=data.min_temp,        # Min temperature
                time_stamp=data.time_stamp     # Time stamp for when the info was pulled off the sensors
            )

            # Serialize the Packet
            serialized_packet = packet.serialize()
            queued_packet_info = Packet_Info(serialized_packet, packet.pac_id)
            q4.put(queued_packet_info)
            # if prog_mode != 0:
            #     print("CP: PACKET PUT ON Q4")

            if pac_id_to_create == UNSIGNED_INT_MAX:
                pac_id_to_create = 1
            else:
                pac_id_to_create += 1

        time.sleep(2)



########################################################################
#   Function Name: send_packet                                         #
#   Author: Robb Northrup                                              #
#   Parameters: queue <thermal_data> (from create_packet())            #                               
#   Description: Send serialized packets over RF to the GCS            #                            
#   Return: None                                                       #
########################################################################
def send_packet(q4, my_packet_info_dict, prog_mode, q_log):
    pid = os.getpid()
    
    if hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(pid, {3})
    
    udp_socket = None
    if prog_mode == 2:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        # ////////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
        #       COMPUTE PRIORITY WEIGHT FOR RESENDING TIMED OUT PACKETS
        #                   (from my_packet_info_dict)
        # \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\//////////////////////////////////////
        size_unacked_pacs = my_packet_info_dict.size()
        size_new_pacs = q4.qsize()  # Using qsize() for queue size
        if prog_mode != 0:
            print(f"SP: Q_NEWPAC_SIZE = {size_new_pacs}  |   Q_UNACKPAC_SIZE: {size_unacked_pacs}")
        size_total_pac_queues = size_unacked_pacs + size_new_pacs
        resend_priority = (size_unacked_pacs / size_total_pac_queues) if size_total_pac_queues > 0 else 0  # Prevent div by zero
        # ----------Why Random?----------
        # I included "rand_float" b/c it introduces a probabilistic element that prioritizes new
        # packets when there are fewer unACKed packets and increases resends when there are more
        rand_float = random.random()


        # Resend unACKed, timed-out packets
        if my_packet_info_dict.check_top_timeout() and (rand_float < resend_priority):
            inc_ack_pac = None # To be set in the following lines based off of mode (RF/UDP socket)

            if prog_mode != 0:
                print(f"SP: ID {my_packet_info_dict.peek_top_pac_id()} timed out")

            #for saving to pac_info_dict
            ser_pac_to_send_info = my_packet_info_dict.peek_top_packet_info()
            ser_pac_to_send = ser_pac_to_send_info.serialized_packet
            
            #remove from pac_info_dict
            my_packet_info_dict.pop(ser_pac_to_send_info.pac_id) # remove from dictionary (to be added again once resent)

            if prog_mode != 0:
                print(f"SP: PACKET {ser_pac_to_send_info.get_pac_id()} RESENDING . . .")
        
            try:
                if prog_mode != 2:
                    rf_serial.flush()
                    rf_serial.write(ser_pac_to_send)
                else:
                    udp_socket.sendto(ser_pac_to_send, GCS_ADDRESS)
                
                # --- #
                # LOG #
                # --- #
                ser_pac_to_send_info.set_timestamp(time.time_ns())
                #for logging
                id_pac_to_send = ser_pac_to_send_info.get_pac_id()
                trans_pac_to_send = ser_pac_to_send_info.get_transmissions()       
                log_trans_drone(id_pac_to_send, "DAT", "s", trans_pac_to_send, q4.qsize(), my_packet_info_dict.size(), q_log)
                
                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.pac_id} RESENT AT {ser_pac_to_send_info.get_timestamp()}")

                    pac_id, lat, lon, alt, high_temp, low_temp, time_stamp = struct.unpack('<IffIhhq', ser_pac_to_send[:-4])
                    sent_packet = Packet(
                        pac_id=pac_id,
                        gps_data=[lat, lon],
                        alt=alt,
                        high_temp=high_temp,
                        low_temp=low_temp,
                        time_stamp=time_stamp
                    )
                    print(sent_packet)
                
                # ---------------- #
                # HANDSHAKE METHOD #
                # ---------------- #
                my_packet_info_dict.add(ser_pac_to_send_info)
                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.pac_id} PUT ON PACKET_INFO_DICT")

            except serial.SerialException as e:
                print(f"Failed to send packet: {e}")


        # Send packets if available and resend_priority is insufficient (as compared to random float)
        elif not q4.empty():
            ser_pac_to_send_info = q4.get()
            ser_pac_to_send = ser_pac_to_send_info.serialized_packet
            
            try:
                if prog_mode != 2:
                    rf_serial.flush()
                    rf_serial.write(ser_pac_to_send)
                else:
                    udp_socket.sendto(ser_pac_to_send, GCS_ADDRESS)
                
                ser_pac_to_send_info.set_timestamp(time.time_ns())
                #for logging
                id_pac_to_send = ser_pac_to_send_info.get_pac_id()
                trans_pac_to_send = ser_pac_to_send_info.get_transmissions()

                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.pac_id} SENT AT {ser_pac_to_send_info.get_timestamp()}")

                    pac_id, lat, lon, alt, high_temp, low_temp, time_stamp = struct.unpack('<IffIhhq', ser_pac_to_send[:-4])
                    sent_packet = Packet(
                        pac_id=pac_id,
                        gps_data=[lat, lon],
                        alt=alt,
                        high_temp=high_temp,
                        low_temp=low_temp,
                        time_stamp=time_stamp
                    )
                    print(sent_packet)
                
                # ---------------- #
                # HANDSHAKE METHOD #
                # ---------------- #
                my_packet_info_dict.add(ser_pac_to_send_info)
                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.pac_id} PUT ON PACKET_INFO_DICT")

                # --- #
                # LOG #
                # --- #
                log_trans_drone(id_pac_to_send, "DAT", "s", trans_pac_to_send, q4.qsize(), my_packet_info_dict.size(), q_log)
                
                
            except serial.SerialException as e:
                print(f"Failed to send packet: {e}")
        
        

        # if q4 is empty and packet_info_dict elements have not timed out . . .
        else:
            pass
        
        time.sleep(2)



# /////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\
# ||| CURRENTLY UNINCORPORATED INTO THE BUILD!!! |||
# \\\\\\\\\\\\\\\\\\\\\\\\\/////////////////////////
########################################################################
#   Function Name: transmit_packet()                                   #
#   Author: Robb Northrup                                              #
#   Parameters:                                                        #                               
#   Description:                                                       #                            
#   Return: None                                                       #
########################################################################
def transmit_packet(ser_pac_to_send_info, q_unack_pac_info, udp_socket):
    ser_pac_to_send = ser_pac_to_send_info.serialized_packet

    if prog_mode != 0:
        print(f"TRANSMITTING PACKET {ser_pac_to_send_info.pac_id}")

    try:
        if prog_mode != 2:  # Mode 0|1: Normal transmission over RF
            rf_serial.flush()
            rf_serial.write(ser_pac_to_send)  # Send bytes over the RF module
        else:  # Debug mode, send over UDP
            udp_socket.sendto(ser_pac_to_send, GCS_ADDRESS)

        ser_pac_to_send_info.set_timestamp(time.time_ns())

        if prog_mode != 0:
            print(f"{ser_pac_to_send_info.pac_id} SENT AT {ser_pac_to_send_info.get_timestamp()}")

        q_unack_pac_info.put(ser_pac_to_send_info)

        # Extract payload (excluding checksum, assuming last 4 bytes are checksum)
        payload = ser_pac_to_send[:-4]  

        # Handshake Method (ACK Request)
        REQ = struct.pack('<3sI', b"REQ", ser_pac_to_send_info.pac_id)

        if prog_mode != 2:
            rf_serial.write(REQ)
        else:
            udp_socket.sendto(REQ, GCS_ADDRESS)

    except serial.SerialException as e:
        if prog_mode != 0:
            print(f"Failed to send packet: {e}")

    # Deserialize the payload for debugging
    if prog_mode != 0:
        try:
            pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', payload)
            packet = Packet(
                pac_id=pac_id,
                gps_data=[lat, lon],
                alt=alt,
                high_temp=high_temp,
                low_temp=low_temp
            )
            print(packet)
        except struct.error as e:
            print(f"Error unpacking payload: {e}")



########################################################################
#   Function Name: receive_and_decode()                                #
#   Author: Robb Northrup                                              #
#   Parameters:                                                        #                               
#   Description:                                                       #                            
#   Return: None                                                       #
########################################################################
# ONLY NEED Q4 AS AN ARGUMENT B/C LOGGER NEEDS TO BE REENCAPSULATED
def receive_and_decode(my_packet_info_dict, prog_mode, q4, q_log):
    # UDP socket debug mode (local)
    if prog_mode == 2:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("127.0.0.1", UDP_PORT))
        print(f"RD: Listening for packets on UDP Port {UDP_PORT}...")
        data = None
        addr = None

    # Mode 0|1: Read from RF serial
    else:
        try:
            # Open the serial port connected to the RF module
            print(f"RD: Listening for packets on /dev/ttyUSB{rf_serial}...")
        except serial.SerialException as e:
            print(f"RD: Error opening serial port: {e}")
            return
        
    # Program loop for receiving, deserializing, receiving ACKs, and taking it off
    # my_packet_info_dict
    while True:
        try:
            # Receive the data off the bus
            if prog_mode == 2:
                print("RD: Reading off the UDP socket . . .")
                data, addr = udp_socket.recvfrom(ACK_PACKET_SIZE)
                
                #print(f"RD: Received packet from {addr}")
            # Read the serialized data from the RF module
            else:
                data = rf_serial.read(ACK_PACKET_SIZE)
                if prog_mode == 1:
                    #print(f"RD: received packet from {rf_serial_usb_port}")
                    pass

            # if prog_mode != 0:
            #     print(f"RD: PACKET LENGTH: {len(data)}")
            #     print(f'RD: PACKET RECEIVED: {data.hex()}')  # Print as hex for readability
            
            if len(data) < ACK_PACKET_SIZE:
                if prog_mode != 0:
                    print("RD: Incomplete packet received, skipping...")
                continue


            # Unpack the payload and checksum
            ack_payload = data[:-4]  # setting to all but the sum . . . 
            received_checksum = struct.unpack('<I', data[-4:])[0] # and here we check that sum

            computed_checksum = zlib.crc32(ack_payload)

            if computed_checksum != received_checksum:
                print(f"RD: Checksum mismatch! Packet corrupted. \\ COMPUTED:{computed_checksum}, RECEIVED: {received_checksum}")
                continue

            # DESERIALIZE THE PAYLOAD, PUT BACK INTO A PACKET
            type, pac_id = struct.unpack('<3sI', ack_payload)
            if prog_mode != 0:
                print(f"RD: RECEIVED ACK FOR PACKET ID {pac_id}")

            successfully_pop_pac = my_packet_info_dict.pop(pac_id) # True/false value if popped pac_id off of the my_packet_info_dict struct
            if prog_mode != 0:
                if successfully_pop_pac == True:
                    print(f"RD: SUCCESSFULLY POPPED PACKET ID {pac_id} OFF OF MY_PACKET_INFO_DICT")
                else:
                    print(f"RD: FAILED TO POP PACKET ID {pac_id} OFF OF MY_PACKET_INFO_DICT")

            # --- #
            # LOG #
            # --- #
            log_trans_drone(pac_id, "ACK", "r", 1, q4.qsize(), my_packet_info_dict.size(), q_log)
                    

        except struct.error as e:
            print(f"RD: Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"RD: Serial communication error: {e}")



# This is a custom manager to support the Packet_Info_Dict instance
class MyManager(mp.managers.BaseManager):
    pass

MyManager.register('Packet_Info_Dict', Packet_Info_Dict)



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
        writer.writerow(["timestamp", "packet_id", "pac_type", "send(s)/receive(r)", "trans_type", "num_transmissions", "unsent_pac_queue_size", "unacked_pac_queue_size"])  # Define CSV headers

def radio_log_listener(q_log, csv_file):
    """Process that listens for logs and writes them to CSV."""
    setup_csv_logger(csv_file)
    
    with open(csv_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        
        while True:
            try:
                record = q_log.get()
                if record is None:
                    break  # Stop listener when None is received
                
                writer.writerow([record["timestamp"], record["packet_id"], record["pac_type"], record["send(s)/receive(r)"], record["trans_type"], record["num_transmissions"], record["unsent_pac_queue_size"], record["unacked_pac_queue_size"]])
                file.flush()  # Flush immediately to prevent data loss
            
            except Exception as e:
                print("Logging error:", e)

def log_trans_drone(pac_id, pac_type, send_or_recieve, num_transmissions, unsent_pac_queue_size, unacked_pac_queue_size, q_log):
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
    q_log.put({"timestamp": timestamp, "pac_type": pac_type, "packet_id": pac_id, "send(s)/receive(r)": send_or_recieve, "pac_type": pac_type, "trans_type": trans_type,  "num_transmissions": num_transmissions, "unsent_pac_queue_size": unsent_pac_queue_size, "unacked_pac_queue_size": unacked_pac_queue_size})




########################################################################
#   Function Name: __main__()                                          #
#   Author: Chris Zinser, Robb Northrup                                #
#   Parameters:  none                                                  #                               
#   Description: This is the main thread for the program. This thread  #
#                takes in frames from the thermal camera and places    #
#                the frames in a queue for further processing. All     #
#                processes are also created from this thread as well   #
#                as device setup for periphials                        #                            
#   Return: None                                                       #
########################################################################
if __name__ == '__main__':
    mp.set_start_method('spawn')    # 'spawn' : for windows deployment (and safe on linux)
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

    prog_mode = 0
    my_packet_info_dict = Packet_Info_Dict()

    parser = argparse.ArgumentParser(description="Provide the mode of the program you wish to run.")
    parser.add_argument("--mode", type=int, help="MODES: 0-Basic | 1-Debug | 2-Local Sys Debug")
    args = parser.parse_args()
    if args.mode is not None:  # Avoid overwriting if mode isn't provided
        prog_mode = args.mode

    if prog_mode != 0:
        print(f"RUNNING IN PROG MODE: {prog_mode}")
        print("TEST_MAIN 1")

    pid = os.getpid()
    os.sched_setaffinity(pid, {0})
    
    # Set parameters to communicate with thermal camera
    if prog_mode != 0:
        print("TEST_MAIN 2")
    if prog_mode != 2:
        rf_serial = serial.Serial(port=RF_TRANCIEVER_PORT, baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
        i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
    
    # Initialize thermal camera
    if prog_mode != 2:
        mlx = adafruit_mlx90640.MLX90640(i2c)
        if prog_mode == 1:
            print("MLX addr detected on I2C")
            print([hex(i) for i in mlx.serial_number])

    # Adjust thermal cameras refresh rate
    if prog_mode != 2:
        mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
    frame = [0] * 768

    # Initialize shared memory between queues
    if prog_mode != 0:
        print("TEST_MAIN 3")

    # =============================
    # Note on "mp.Manager()" usage:
    # =============================
    #   This is new to the radio v3 build where I need a shared instance of
    #   my_packet_info_dict to keep track of unacknowledged, sent packets
    #   (for retransmission should they timeout).
    #
    #   This is a slower, but necessary means of sharing mutable objects between
    #   proccesses (it is managed via a server proccess, which itself introduces
    #   overhead).
    #
    #   POSSIBLE ALTERNATIVE SOLUTION?

    with MyManager() as manager:
        my_packet_info_dict = manager.Packet_Info_Dict() # Create shared instance of dict

        q1 = mp.Queue()
        q2 = mp.Queue()
        q3 = mp.Queue()
        q4 = mp.Queue()
        q5 = mp.Queue() # simulation queue
        q_log = mp.Queue() # queue for storing logs

        # Initialize threads for processing and transmitting radio data
        if prog_mode != 0:
            print("TEST_MAIN 4")
        p1 = mp.Process(target=data_structure_builder, args=(q1,q2,q5,))
        p2 = mp.Process(target=data_processing, args=(q2,q3,))
        p3 = mp.Process(target=create_packet, args=(q3,q4,))
        p4 = mp.Process(target=send_packet, args=(q4,my_packet_info_dict,prog_mode,q_log,))
        p5 = mp.Process(target=gps_sim, args=(q5,)) # sim flight queue
        p_recieve_packets = mp.Process(target=receive_and_decode, args=(my_packet_info_dict,prog_mode,q4,q_log,))
        p_logger_radio = mp.Process(target=radio_log_listener, args=(q_log, get_flight_log_filename()))

        # Start threads
        if prog_mode != 0:
            print("TEST_MAIN 5")
        p1.start()
        p2.start()
        p3.start()
        p4.start()
        p5.start()
        p_recieve_packets.start()
        p_logger_radio.start()
        
        #print(q.get())
        #p.join()
        
        #Frame retrieval from mlx 90640
        while True:
            #stamp = time.monotonic()
            try:
                if prog_mode != 2:			# q_unack_pac_info.put(ser_pac_to_send_info)
                    # if prog_mode != 0:
                    #     print(f"SP: PACKET {ser_pac_to_send_info.pac_id} PUT ON Q_UNACK_PAC_INFO")
                    mlx.getFrame(frame)
                q1.put(frame)
                #print("Main Thread running on core:",os.sched_getaffinity(pid)  )
            except ValueError:
                continue
