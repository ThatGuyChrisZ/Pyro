import struct
import zlib
import sys
import serial
import json
import time
import random
import requests
from packet_class._v2.packet import Packet

PACKET_SIZE = 24  # Adjust if necessary

USE_SIMULATED_PACKETS = True  # Set to False for real RF input
SERIAL_PORT = "/dev/ttyUSB0" 
BAUD_RATE = 57600
SIMULATED_PACKET_INTERVAL = 2 

def send_packet_to_server(packet):
    server_url = "http://localhost:8000/add_packet"
    try:
        packet_data = {
            "pac_id": packet.pac_id,
            "gps_data": packet.gps_data,
            "alt": packet.alt,
            "high_temp": packet.high_temp,
            "low_temp": packet.low_temp,
        }

        response = requests.post(server_url, json=packet_data)
        if response.status_code == 200:
            print("Packet successfully sent to server.")
        else:
            print(f"Failed to send packet to server. Status code: {response.status_code}, Response: {response.text}")
    except requests.RequestException as e:
        print(f"Error connecting to the server: {e}")

# Function to simulate receiving packets
def generate_simulated_packet():
    pac_id = random.randint(1000, 9999)
    lat = round(39.5296 + random.uniform(-0.01, 0.01), 6) 
    lon = round(-119.8138 + random.uniform(-0.01, 0.01), 6)
    alt = random.randint(500, 2000) 
    high_temp = random.randint(300, 800) 
    low_temp = random.randint(250, 400) 

    # Serialize packet like actual RF transmission
    payload = struct.pack('<IffIhh', pac_id, lat, lon, alt, high_temp, low_temp)
    checksum = zlib.crc32(payload)
    serialized_packet = payload + struct.pack('<I', checksum)

    print(f"🔥 Simulated Packet Sent - ID: {pac_id}, Location: ({lat}, {lon}), Alt: {alt}, Temp: {high_temp}-{low_temp}°F")
    return serialized_packet

def receive_and_decode_packets():
    global USE_SIMULATED_PACKETS

    if USE_SIMULATED_PACKETS:
        print("Running in SIMULATION mode (No RF required).")
        while True:
            time.sleep(SIMULATED_PACKET_INTERVAL) 
            packet_data = generate_simulated_packet()
            process_received_packet(packet_data)

    else:
        # Try to open the RF serial port
        try:
            rf_serial = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=10, rtscts=True, dsrdtr=True)
            print(f"📡 Listening for packets on {SERIAL_PORT}...")

            while True:
                data = rf_serial.read(PACKET_SIZE)
                if len(data) < PACKET_SIZE:
                    print("⚠ Incomplete packet received, skipping...")
                    continue

                process_received_packet(data)

        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            print("Switching to SIMULATION mode...")
            USE_SIMULATED_PACKETS = True
            receive_and_decode_packets()

# Made into new function, originally in receive_and_decode
def process_received_packet(data):
    try:
        print(f"\nReceived Packet: {data.hex()}")

        payload = data[:-4]
        received_checksum = struct.unpack('<I', data[-4:])[0] 
        computed_checksum = zlib.crc32(payload)

        if computed_checksum != received_checksum:
            print(f"Checksum mismatch! Packet corrupted. (Computed: {computed_checksum}, Received: {received_checksum})")
            return

        pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', payload)

        packet = Packet(
            pac_id=pac_id,
            gps_data=[lat, lon],
            alt=alt,
            high_temp=high_temp,
            low_temp=low_temp
        )

        print(f"Packet Decoded: {packet}")
        send_packet_to_server(packet)

    except struct.error as e:
        print(f"Error decoding packet: {e}")

if __name__ == '__main__':
    receive_and_decode_packets()