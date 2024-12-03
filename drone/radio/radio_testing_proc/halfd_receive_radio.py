import sys
import serial
import struct
import time

DEBUG = False
SERIAL_PORT = '/dev/ttyUSB1'  # Adjust as necessary
BAUD_RATE = 57600

def receive_data():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    if DEBUG:
        import random
    reject_chance = 0
    debug_reject_chance = 25

    try:
        while True:
            # Wait until data is available to read
            if ser.in_waiting == 0:
                time.sleep(0.1)
                continue

            # Read the data type prefix
            header = ser.read(3)  # Read 3 bytes

            # Read packet ID
            packet_id_data = ser.read(2)
            if len(packet_id_data) < 2:
                continue  # Incomplete data, skip
            packet_id, = struct.unpack('!H', packet_id_data)

            if header == b'GPS':
                # Read GPS data (3 floats = 12 bytes)
                data = ser.read(12)
                if len(data) < 12:
                    continue  # Incomplete data, skip
                latitude, longitude, altitude = struct.unpack('!fff', data)
                print(f'Received GPS Data - ID: {packet_id}, Latitude: {latitude}, Longitude: {longitude}, Altitude: {altitude}')

                # Wait for a short period to ensure sender has switched to receive mode
                time.sleep(0.5)

                # Send ACK
                ack_packet = b'ACK' + struct.pack('!H', packet_id)
                ser.write(ack_packet)
                print(f'Sent ACK for GPS packet ID {packet_id}')

            elif header == b'IMG':
                # Read image data
                image_data = b''
                while True:
                    chunk = ser.read(1024)
                    if not chunk:
                        break
                    image_data += chunk
                    if len(chunk) < 1024:
                        break  # Assuming end of image data

                with open(f'received_image_{packet_id}.png', 'wb') as f:
                    f.write(image_data)
                print(f'Received image data with ID {packet_id} and saved to received_image_{packet_id}.png')

                # **Wait for a short period to ensure sender has switched to receive mode**
                time.sleep(0.5)

                # Send ACK
                ack_packet = b'ACK' + struct.pack('!H', packet_id)
                ser.write(ack_packet)
                print(f'Sent ACK for image packet ID {packet_id}')

            else:
                # Unknown header, discard data
                print('Received unknown data type')
                continue

            # **Important Modification Ends Here**

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        DEBUG = True
    receive_data()
