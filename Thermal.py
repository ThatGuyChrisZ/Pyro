print("test")

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
## import board
## import busio
## import adafruit_mlx90640
import multiprocessing as mp
# import ctypes
import serial # for serial communication over usb
from thermal_data import thermal_data
from radio.packet_class._v2.packet import Packet

# packet_lib = ctypes.CDLL('./packet_class/packet.so')
rf_serial = serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=1)

# Take thermal data, add GPS + alt data
def data_structure_builder(q,q2):
	while True:
		if q.empty() == False:
			thermal = thermal_data(q.get())
			q2.put(thermal)

# Find min + max of frames
def data_processing(q2,q3):
	while True:
		if q2.empty() == False:
			q3.put(q2.get())

# Compartmentalize data in packet, serialize, and send
def send_packet(q3):
    while True:
        if not q3.empty():
            print("Data on thread 3")

            # Get data from the queue
            data = q3.get()

            # Create a Packet object
            packet = Packet(
                pac_id=data.packet_id,         # Example: unique ID
                gps_data=data.gps,             # GPS coordinates [latitude, longitude]
                alt=data.barometric,           # Altitude in meters
                high_temp=data.max_temp,       # Max temperature
                low_temp=data.min_temp         # Min temperature
            )

            # Serialize the Packet
            serialized_packet = packet.serialize()

            # Send the serialized packet over RF
            try:
                rf_serial.write(serialized_packet)  # Send bytes over the RF module
                print(f'Packet sent: {serialized_packet.hex()}')  # Print as hex for readability
            except serial.SerialException as e:
                print(f"Failed to send packet: {e}")


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
	q = mp.Queue()
	q2 = mp.Queue()
	q3 = mp.Queue()
	p = mp.Process(target=data_structure_builder, args=(q,q2,))
	p2 = mp.Process(target=data_processing, args=(q2,q3,))
	p3 = mp.Process(target=send_packet, args=(q3,))
	p.start()
	p2.start()
	p3.start()
    #print(q.get())
    #p.join()
	while True:
		#stamp = time.monotonic()
		try:			
			## mlx.getFrame(frame)
			q.put(frame)
		except ValueError:
			continue