print("test")

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import busio
import adafruit_mlx90640
import multiprocessing as mp
import ctypes
import pyserial # for serial communication over usb
from thermal_data import thermal_data
from '\packet_class\\_v2\\packet.py' import Packet

packet_lib = ctypes.CDLL('./packet_class/packet.so')

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
		if q3.empty() == False:
			print("Data on thread 3")
			data = q3.get()
			
			
            # Call the cpp function with the data 
			packet = packet_lib.create_packet(ctypes.c_uint(), (ctypes.c_float * 2)(*data.gps), ctypes.c_float(data.barometric), ctypes.c_float(data.max_temp), ctypes.c_float(data.min_temp))
			
            # packet data -> byte array, send over radio
			byte_packet = bytes(packet.contents)
			# send_radio(byte_packet) # IMPLEMENT MEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
			print('Packet sent: ', byte_packet)


if __name__ == '__main__':
	PRINT_TEMPERATURES = True
	PRINT_ASCIIART = False

	i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
	# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

	mlx = adafruit_mlx90640.MLX90640(i2c)
	print("MLX addr detected on I2C")
	print([hex(i) for i in mlx.serial_number])

	mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
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
			mlx.getFrame(frame)
			q.put(frame)
		except ValueError:
			continue