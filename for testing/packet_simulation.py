import struct
import zlib
import requests
import random

# Define a packet structure consistent with `packet_receiver.py`
PACKET_SIZE = 24

def generate_packet(pac_id):
    # Randomized data for GPS, altitude, and temperature
    lat = random.uniform(-90, 90)
    lon = random.uniform(-180, 180)
    alt = random.randint(0, 10000)  # Altitude in meters
    high_temp = random.randint(30, 120)  # High temperature in Fahrenheit
    low_temp = random.randint(-20, 29)  # Low temperature in Fahrenheit

    # Pack the payload
    payload = struct.pack('<IffIhh', pac_id, lat, lon, alt, high_temp, low_temp)

    # Calculate checksum
    checksum = zlib.crc32(payload)

    # Append the checksum to the payload
    packet_data = payload + struct.pack('<I', checksum)
    return packet_data

def send_packet(packet_data):
    """Sends a simulated packet to the packet receiver endpoint."""
    try:
        # Extracting fields for debugging
        payload = packet_data[:-4]
        pac_id, lat, lon, alt, high_temp, low_temp = struct.unpack('<IffIhh', payload)

        # Create a simulated server-like response
        server_url = "http://localhost:8000/add_packet"  # Update this if server URL changes
        packet_info = {
            "pac_id": pac_id,
            "gps_data": [lat, lon],
            "alt": alt,
            "high_temp": high_temp,
            "low_temp": low_temp
        }
        
        response = requests.post(server_url, json=packet_info)
        if response.status_code == 200:
            print(f"Packet {pac_id} sent successfully. Response: {response.json()}")
        else:
            print(f"Failed to send packet {pac_id}. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending packet: {e}")

def main():
    """Simulate and send multiple packets to test the system."""
    for pac_id in range(1, 6):  # Simulating 5 packets
        packet = generate_packet(pac_id)
        print(f"Generated Packet {pac_id}: {packet.hex()}")
        send_packet(packet)

if __name__ == "__main__":
    main()
