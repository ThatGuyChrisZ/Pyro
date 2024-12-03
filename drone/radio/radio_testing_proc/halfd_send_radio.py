import sys
import serial
import time
import struct

DEBUG = False
SERIAL_PORT = '/dev/ttyUSB0'  # Adjust as necessary
# SERIAL_PORT = '/dev/ttys004' # MacOS debug
BAUD_RATE = 57600  # Adjust as necessary

def send_data():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    packet_id = 0  # Initialize packet ID
    image_nack_list = []  # List to store packet IDs that did not receive an ACK
    gps_nack_list = []  # List to store packet IDs that did not receive an ACK

    try:
        while True:
            # Increment packet ID
            packet_id += 1

            # Mock GPS data
            gps_data = {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 30.0
            }

            # Load image data
            with open('shrek.png', 'rb') as f:
                image_data = f.read()

            # Serialize GPS data with packet ID
            gps_packet = struct.pack('!Hfff', packet_id, gps_data['latitude'], gps_data['longitude'], gps_data['altitude'])

            # Send GPS data with ID
            ser.write(b'GPS' + gps_packet)
            print(f'Sent GPS data with ID {packet_id}')

            # Wait for the receiver to process and switch to transmit mode
            time.sleep(0.5)  # Adjust delay as necessary based on radio characteristics

            # Flush the input buffer before listening for ACK
            ser.flushInput()

            # Listen for ACK
            ack_received = False
            start_time = time.time()
            while time.time() - start_time < 5:
                # Now switch to receive mode
                if ser.in_waiting > 0:
                    ack_packet = ser.read(5)
                    if ack_packet.startswith(b'ACK'):
                        ack_id = struct.unpack('!H', ack_packet[3:5])[0]
                        if ack_id == packet_id:
                            print(f'Received ACK for packet ID {ack_id}')
                            ack_received = True
                            break
                time.sleep(0.1)  # Small delay to prevent busy-waiting

            if not ack_received:
                gps_nack_list.append(packet_id)
                print(f'No ACK received for GPS packet ID {packet_id}')

            # Repeat the process for image data

            # Send image data with ID
            image_packet = struct.pack('!H', packet_id) + image_data
            ser.write(b'IMG' + image_packet)
            print(f'Sent image data with ID {packet_id}')

            # Wait for the receiver to process and switch to transmit mode
            time.sleep(0.5)  # TODO Adjust delay as necessary

            # Flush the input buffer before listening for ACK
            ser.flushInput()

            # Listen for ACK
            ack_received = False
            start_time = time.time()
            while time.time() - start_time < 5:
                if ser.in_waiting > 0:
                    ack_packet = ser.read(5)
                    if ack_packet.startswith(b'ACK'):
                        ack_id = struct.unpack('!H', ack_packet[3:5])[0]
                        if ack_id == packet_id:
                            print(f'Received ACK for packet ID {ack_id}')
                            ack_received = True
                            break
                time.sleep(0.1)

            if not ack_received:
                image_nack_list.append(packet_id)
                print(f'No ACK received for image packet ID {packet_id}')

            # Wait before sending the next packet
            time.sleep(3)

    except KeyboardInterrupt:
        pass
    finally:
        print('Packets without GPS ACK:', gps_nack_list)
        print('Packets without image ACK:', image_nack_list)
        ser.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        DEBUG = True
    send_data()
