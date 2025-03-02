import struct
import zlib
import time
import serial
import serial.tools.list_ports
import requests
from packet_class._v2.packet import Packet

PACKET_SIZE = 24
BAUD_RATE = 57600
SIMULATED_SERIAL_PORT = "loop://"

def send_packet_to_server(packet):
    """Sends the decoded packet to the server."""
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
            print("✅ Packet successfully sent to server.")
        else:
            print(f"❌ Failed to send packet. Status code: {response.status_code}, Response: {response.text}")
    except requests.RequestException as e:
        print(f"❌ Error connecting to the server: {e}")

def process_received_packet(data):
    """Processes received packet data."""
    try:
        print(f"\nReceived Packet: {data.hex()}")

        payload = data[:-4]
        received_checksum = struct.unpack('<I', data[-4:])[0]
        computed_checksum = zlib.crc32(payload)

        if computed_checksum != received_checksum:
            print(f"Checksum mismatch! (Computed: {computed_checksum}, Received: {received_checksum})")
            return

        pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', payload)

        packet = Packet(
            pac_id=pac_id,
            gps_data=[lat, lon],
            alt=alt,
            high_temp=high_temp,
            low_temp=low_temp
        )

        print(f"✅ Packet Decoded: {packet}")
        send_packet_to_server(packet)

    except struct.error as e:
        print(f"❌ Error decoding packet: {e}")

def receive_and_decode_packets():
    """Listens for packets sent via the virtual serial port."""
    print("Running in SIMULATION mode (No RF required).")
    try:
        with serial.serial_for_url(SIMULATED_SERIAL_PORT, BAUD_RATE, timeout=10) as ser:
            print(f"Listening for packets on {SIMULATED_SERIAL_PORT}...")

            while True:
                data = ser.read(PACKET_SIZE)
                if len(data) == 0:
                    print("Waiting for data...")
                    continue

                process_received_packet(data)

    except serial.SerialException as e:
        print(f"❌ Error opening virtual serial port: {e}")
        print("Ensure the test script is running.")

if __name__ == '__main__':
    receive_and_decode_packets()