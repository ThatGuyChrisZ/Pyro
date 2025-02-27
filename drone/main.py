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
from thermal_data import thermal_data
from radio.packet_class._v3.packet import Packet, Packet_Info, Packet_Info_Dict

pac_id_to_create = 1 # Global variable for creating the next packet id (don't kill me)
UNSIGNED_INT_MAX = 2147483647

# rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
ACK_PACKET_SIZE = (3 + 4) # String (of three letters) + integer size
GCS_ADDRESS = ("127.0.0.1", 5005)  # Localhost UDP port
gps_sim_file = open('sim_gps.txt', 'r')
UDP_PORT = 5004
# alt_sim_file = open('alt_gps.txt', 'r')
# packet_lib = ctypes.CDLL('./packet_class/packet.so')



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
                low_temp=data.min_temp         # Min temperature
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



########################################################################
#   Function Name: send_packet                                         #
#   Author: Robb Northrup                                              #
#   Parameters: queue <thermal_data> (from create_packet())            #                               
#   Description: Send serialized packets over RF to the GCS            #                            
#   Return: None                                                       #
########################################################################
def send_packet(q4, my_packet_info_dict, prog_mode, rf_serial):
    pid = os.getpid()
    
    if hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(pid, {3})
    
    udp_socket = None
    if prog_mode == 2:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        # Send packets if available and no un-ACKed packets exist
        if not q4.empty() and not my_packet_info_dict.check_top_timeout():
            ser_pac_to_send_info = q4.get()
            ser_pac_to_send = ser_pac_to_send_info.serialized_packet
            
            try:
                if prog_mode != 2:
                    rf_serial.flush()
                    rf_serial.write(ser_pac_to_send)
                else:
                    udp_socket.sendto(ser_pac_to_send, GCS_ADDRESS)
                
                ser_pac_to_send_info.set_timestamp(time.time_ns())
                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.pac_id} SENT AT {ser_pac_to_send_info.get_timestamp()}")

                    pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', ser_pac_to_send[:-4])
                    sent_packet = Packet(
                        pac_id=pac_id,
                        gps_data=[lat, lon],
                        alt=alt,
                        high_temp=high_temp,
                        low_temp=low_temp
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
        
        # Resend unACKed, timed-out packets
        elif my_packet_info_dict.check_top_timeout():
            inc_ack_pac = None # To be set in the following lines based off of mode (RF/UDP socket)

            if prog_mode != 0:
                print(f"SP: ID {my_packet_info_dict.peek_top_pac_id()} timed out")

            # IF STATEMENT REDUNDANT
            if my_packet_info_dict.check_top_timeout() is True:
                # REQ = struct.pack('<3sI', b"REQ", my_packet_info_dict.peek_top_pac_id())
                # if prog_mode != 2:
                #     rf_serial.write(REQ)
                # else:
                #     udp_socket.sendto(REQ, GCS_ADDRESS)
                # if prog_mode != 0:
                #     print(f"SP: PACKET {ser_pac_to_send_info.pac_id} REQ SENT")
                
                ser_pac_to_send_info = my_packet_info_dict.peek_top_packet_info()
                ser_pac_to_send = ser_pac_to_send_info.serialized_packet
                my_packet_info_dict.pop(ser_pac_to_send_info.pac_id) # remove from dictionary (to be added again once resent)

                if prog_mode != 0:
                    print(f"SP: PACKET {ser_pac_to_send_info.get_pac_id()} RESENDING . . .")
            
                try:
                    if prog_mode != 2:
                        rf_serial.flush()
                        rf_serial.write(ser_pac_to_send)
                    else:
                        udp_socket.sendto(ser_pac_to_send, GCS_ADDRESS)
                    
                    ser_pac_to_send_info.set_timestamp(time.time_ns())
                    if prog_mode != 0:
                        print(f"SP: PACKET {ser_pac_to_send_info.pac_id} RESENT AT {ser_pac_to_send_info.get_timestamp()}")

                        pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', ser_pac_to_send[:-4])
                        sent_packet = Packet(
                            pac_id=pac_id,
                            gps_data=[lat, lon],
                            alt=alt,
                            high_temp=high_temp,
                            low_temp=low_temp
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

            # Attempt to remove packets off the dict queue (MOVED TO NEW PROCESS: RECEIVE_AND_DECODE())
            # try:
            #     print("eek1")
            #     if prog_mode != 2:
            #         inc_ack_pac = rf_serial.read(ACK_PACKET_SIZE)
            #         print('eek2')
            #     else:
            #         print('eek3')
            #         # BROKEN LINE OF CODE!!!!
            #         inc_ack_pac, addr = udp_socket.recvfrom(ACK_PACKET_SIZE)
                
            #     print("eajdklajfl")
            #     if prog_mode != 2:
            #         print("SP: Reading for ACKs off of rf/udp")
                
            #     if inc_ack_pac is None:
            #         if prog_mode != 0:
            #             print("SP: Waiting on ACK for packets . . .")
            #     elif len(inc_ack_pac) == ACK_PACKET_SIZE:
            #         inc_ack_pac_id = struct.unpack('<I', inc_ack_pac[3:])[0]  # Extract packet ID
                    
            #         # Remove acknowledged packet from queue
            #         if not my_packet_info_dict.is_empty():
            #             my_packet_info_dict.pop(inc_ack_pac_id)
            #         else: # if recieved ACK for a packet that is not held in dict
            #             # IMPLEMENT MEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE!
            #             pass
            #     else:
            #         print(f"Warning: Incomplete ACK received ({len(inc_ack_pac)} bytes)")
        
            # except serial.SerialException as e:
            #     print(f"Error reading ACK: {e}")

        # if q4 and packet_info_dict are empty . . .
        else:
            pass
        
        time.sleep(5)



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
def receive_and_decode(my_packet_info_dict, prog_mode, rf_serial_usb_port):
    # UDP socket debug mode (local)
    if prog_mode == 2:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("0.0.0.0", UDP_PORT))
        print(f"RD: Listening for packets on UDP Port {UDP_PORT}...")
        data = None

    # Mode 0|1: Read from RF serial
    else:
        try:
            # Open the serial port connected to the RF module
            print(f"RD: Listening for packets on /dev/ttyUSB{rf_serial_usb_port}...")
        except serial.SerialException as e:
            print(f"RD: Error opening serial port: {e}")
            return
        
    # Program loop for receiving, deserializing, receiving ACKs, and taking it off
    # the my_packet_info_dict
    while True:
        try:
            # Receive the data off the bus
            if prog_mode == 2:
                data, addr = udp_socket.recvfrom(ACK_PACKET_SIZE)
                print(f"RD: Received packet from {addr}")
            # Read the serialized data from the RF module
            else:
                data = rf_serial.read(ACK_PACKET_SIZE)
                if prog_mode == 1:
                    print(f"RD: received packet from {rf_serial_usb_port}")

            if prog_mode != 0:
                print(f"RD: PACKET LENGTH: {len(data)}")
                print(f'RD: PACKET RECEIVED: {data.hex()}')  # Print as hex for readability
                if len(data) < ACK_PACKET_SIZE:
                    print("RD: Incomplete packet received, skipping...")
                    continue

            # Unpack the payload
            payload = data
            # received_checksum = struct.unpack('<I', data[-4:])[0] # and here we check that sum
            # computed_checksum = zlib.crc32(payload)

            # if computed_checksum != received_checksum:
            #     print(f"RD: Checksum mismatch! Packet corrupted. \\ COMPUTED:{computed_checksum}, RECEIVED: {received_checksum}")
            #     continue

            # DESERIALIZE THE PAYLOAD, PUT BACK INTO A PACKET
            type, pac_id = struct.unpack('<3sI', payload)

        except struct.error as e:
            print(f"RD: Error decoding packet: {e}")
        except serial.SerialException as e:
            print(f"RD: Serial communication error: {e}")



# This is a custom manager to support the Packet_Info_Dict instance
class MyManager(mp.managers.BaseManager):
    pass

MyManager.register('Packet_Info_Dict', Packet_Info_Dict)


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
    rf_serial = None
    my_packet_info_dict = Packet_Info_Dict()

    parser = argparse.ArgumentParser(description="Provide the mode of the program you wish to run.")
    parser.add_argument("--mode", type=int, help="MODES: 0-Basic | 1-Debug | 2-Local Sys Debug")
    args = parser.parse_args()
    if args.mode is not None:  # Avoid overwriting if mode isn't provided
        prog_mode = args.mode
    if prog_mode != 2:
        rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER

    if prog_mode != 0:
        print(f"RUNNING IN PROG MODE: {prog_mode}")
        print("TEST_MAIN 1")

    pid = os.getpid()
    os.sched_setaffinity(pid, {0})
    
    # Thermal Camera Settings
    PRINT_TEMPERATURES = True
    PRINT_ASCIIART = False
    
    # Set parameters to communicate with thermal camera
    if prog_mode != 0:
        print("TEST_MAIN 2")
    if prog_mode != 2:
        rf_serial = serial.Serial(port='/dev/ttyUSB1', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER
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

        # Initialize threads for processing and transmitting radio data
        if prog_mode != 0:
            print("TEST_MAIN 4")
        p1 = mp.Process(target=data_structure_builder, args=(q1,q2,q5))
        p2 = mp.Process(target=data_processing, args=(q2,q3,))
        p3 = mp.Process(target=create_packet, args=(q3,q4,))
        p4 = mp.Process(target=send_packet, args=(q4,my_packet_info_dict,prog_mode,rf_serial))
        p5 = mp.Process(target=gps_sim, args=(q5,))
        p_recieve_packets = mp.Process(target=receive_and_decode, args=(my_packet_info_dict,prog_mode,rf_serial,))

        # Start threads
        if prog_mode != 0:
            print("TEST_MAIN 5")
        p1.start()
        p2.start()
        p3.start()
        p4.start()
        p5.start()
        p_recieve_packets.start()
        
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
