# ///////////////////////////////////////////////////
# contributed by Robb Northrup & Ashton Westenburg
# ///////////////////////////////////////////////////


print("test")

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import sys
import board
import busio
import adafruit_mlx90640
import multiprocessing as mp
# import ctypes
import serial # for serial communication over usb
import struct
import zlib
from thermal_data import thermal_data
from radio.packet_class._v2.packet import Packet
gps_sim_file = open('sim_gps.txt', 'r')
#alt_sim_file = open('alt_gps.txt', 'r')




pac_id_to_create = 1 # Global variable for creating the next packet id
UNSIGNED_INT_MAX = 2147483647

# packet_lib = ctypes.CDLL('./packet_class/packet.so')
rf_serial = serial.Serial(port='/dev/ttyUSB0', baudrate=57600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER



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
        #time.sleep(0.2)

# Take thermal data, add GPS + alt data

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
    while True:
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
    # pulls thermal data as available by queue
    while True:
        if q2.empty() == False:
            #pushes data to packet creation
            q3.put(q2.get())

# Compartmentalize data in packet, serialize, and send
def create_packet(q3, q4):
    global pac_id_to_create
    newest = 0
    while True:
        

        
        if not q3.empty():
            # print("Data on thread 3")

            # Get data from the queue
            data = q3.get()
            #print("Data recieved at processing")
            #print(data.max_temp)
            # Create a Packet object
            packet = Packet(
                pac_id=pac_id_to_create,       # Pulled from global variable
                gps_data=data.gps,             # GPS coordinates [latitude, longitude]
                alt=data.barometric,           # Altitude in meters
                high_temp=data.max_temp,       # Max temperature
                low_temp=data.min_temp         # Min temperature
            )

            if pac_id_to_create == UNSIGNED_INT_MAX:
                pac_id_to_create = 1
            else:
                pac_id_to_create += 1

            # Serialize the Packet
            serialized_packet = packet.serialize()
            q4.put(serialized_packet)

def send_packet(q4):
    while True:
        if not q4.empty():
            serialized_packet = q4.get()
            # Send the serialized packet over RF
            try:
                rf_serial.flush()
                rf_serial.write(serialized_packet)  # Send bytes over the RF module
                print(f'Packet sent: {serialized_packet.hex()}')  # Print as hex for readability
                #
                #
                #FOR DEBUGGING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                #
                #
                print(f"DATA LENGTH: {len(serialized_packet)}")
                payload = serialized_packet[:-4]  # setting to all but the sum . . . 
                received_checksum = struct.unpack('<I', serialized_packet[-4:])[0] # and here we check that sum
                computed_checksum = zlib.crc32(payload)
                print(f'~~~~~~~~~~CHECK COMPUTED:{computed_checksum}, RECIEVED: {received_checksum}"')
            except serial.SerialException as e:
                print(f"Failed to send packet: {e}")

        # Unpack the payload and checksum
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

            # Print the decoded packet
            print(packet)

        time.sleep(5)
        
        #
        #
        # FOR DEBUGGING PURPOSES, ONLY SEND PACKET ONCE EVERY SECOND
        #
        #


########################################################################
#   Function Name: main                                                #
#   Author: Chris Zinser                                               #
#   Parameters:  none                                                  #                               
#   Description: This is the main thread for the program. This thread  #
#                takes in frames from the thermal camera and places the#
#                frames in a queue for further processing. All         #
#                processes are also created from this thread as well   #
#                as device setup for periphials                        #                            
#   Return: None                                                       #
########################################################################
if __name__ == '__main__':
    
    #Thermal Camera Settings
    PRINT_TEMPERATURES = True
    PRINT_ASCIIART = False
    
    #Set parameters to communicate with thermal camera
    i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
    
    #Initialize thermal camera
    mlx = adafruit_mlx90640.MLX90640(i2c)
    print("MLX addr detected on I2C")
    print([hex(i) for i in mlx.serial_number])

    #Adjust thermal cameras refresh rate
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
    frame = [0] * 768
    mp.set_start_method('spawn')

    #Initialize shared memory between queues
    q1 = mp.Queue()
    q2 = mp.Queue()
    q3 = mp.Queue()
    q4 = mp.Queue()
    q5 = mp.Queue()  #simulation queue
    
    # This is the queue for serialized packets that are ready for transmission

    #Initialize threads for processing and transmitting radio data
    p1 = mp.Process(target=data_structure_builder, args=(q1,q2, q5))
    p2 = mp.Process(target=data_processing, args=(q2,q3,))
    p3 = mp.Process(target=create_packet, args=(q3, q4,))
    p4 = mp.Process(target=send_packet, args=(q4,))
    p5 = mp.Process(target=gps_sim, args=(q5,))

    #Start threads
    p1.start()
    p2.start()
    p3.start()
    p4.start()
    p5.start()
    
    
    #print(q.get())
    #p.join()
    
    #Frame retrieval from mlx 90640
    while True:
        #stamp = time.monotonic()
        try:			
            mlx.getFrame(frame)
            q1.put(frame)
        except ValueError:
            continue
