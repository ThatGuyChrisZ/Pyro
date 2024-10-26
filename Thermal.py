print("test")

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import busio
import adafruit_mlx90640
import multiprocessing as mp
from thermal_data import thermal_data 

def data_structure_builder(q,q2):
	while True:
		if q.empty() == False:
			thermal = thermal_data(q.get())
			q2.put(thermal)

def data_processing(q2,q3):
	while True:
		if q2.empty() == False:
			q3.put(q2.get())

def results(q3):
	while True:
		if q3.empty() == False:
			print("Data on thread 3")
			print(q3.get().array)


if __name__ == '__main__':
	PRINT_TEMPERATURES = True
	PRINT_ASCIIART = False

	i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
	# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

	mlx = adafruit_mlx90640.MLX90640(i2c)
	print("MLX addr detected on I2C")
	print([hex(i) for i in mlx.serial_number])

	mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
	frame = [0] * 768
	mp.set_start_method('spawn')
	q = mp.Queue()
	q2 = mp.Queue()
	q3 = mp.Queue()
	p = mp.Process(target=data_structure_builder, args=(q,q2,))
	p2 = mp.Process(target=data_processing, args=(q2,q3,))
	p3 = mp.Process(target=results, args=(q3,))
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
			#print("Frame:")
			#print(frame)
		except ValueError:
			# these happen, no biggie - retry
			continue
		#print("Read 2 frames in %0.2f s" % (time.monotonic() - stamp))
		#for h in range(24):
			#for w in range(32):
				#t = frame[h * 32 + w]
				#if PRINT_TEMPERATURES:
					#print("%0.1f, " % t, end="")
					#PRINT_TEMPERATURES
			#print()
		#print()
