print("test")

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import sys
## import board
## import busio
## import adafruit_mlx90640
import multiprocessing as mp
# import ctypes
import serial # for serial communication over usb
import struct
import zlib
from thermal_data import thermal_data
from radio.packet_class._v2.packet import Packet

pac_id_to_create = 1 # Global variable for creating the next packet id
UNSIGNED_INT_MAX = 2147483647

# packet_lib = ctypes.CDLL('./packet_class/packet.so')
rf_serial = serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=10, rtscts=True, dsrdtr=True, write_timeout=10) #ADJUST PORT, BAUDRATE AS NECESSARY, MUST BE THE SAME SETTINGS AS THE OTHER TRANSCIEVER

# Take thermal data, add GPS + alt data
def data_structure_builder(q1,q2):
    while True:
        if q1.empty() == False:
            thermal = thermal_data(q1.get())
            q2.put(thermal)

# Find min + max of frames
def data_processing(q2,q3):
    while True:
        if q2.empty() == False:
            q3.put(q2.get())

# Compartmentalize data in packet, serialize, and send
def create_packet(q3, q4):
    global pac_id_to_create

    while True:
        if not q3.empty():
            # print("Data on thread 3")

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


if __name__ == '__main__':
    PRINT_TEMPERATURES = True
    PRINT_ASCIIART = False

    ## i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

    ## mlx = adafruit_mlx90640.MLX90640(i2c)
    print("MLX addr detected on I2C")
    ## print([hex(i) for i in mlx.serial_number])

    ## mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
    frame = [0] * 768
    mp.set_start_method('spawn')

    q1 = mp.Queue()
    q2 = mp.Queue()
    q3 = mp.Queue()
    q4 = mp.Queue() # This is the queue for serialized packets that are ready for transmission

    p1 = mp.Process(target=data_structure_builder, args=(q1,q2,))
    p2 = mp.Process(target=data_processing, args=(q2,q3,))
    p3 = mp.Process(target=create_packet, args=(q3, q4))
    p4 = mp.Process(target=send_packet, args=(q4,))

    p1.start()
    p2.start()
    p3.start()
    p4.start()

    #print(q.get())
    #p.join()
    
    while True:
        #stamp = time.monotonic()
        try:			
            ## mlx.getFrame(frame)
            q1.put(frame)
        except ValueError:
            continue