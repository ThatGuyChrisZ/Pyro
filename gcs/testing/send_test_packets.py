import unittest
import sqlite3
import time
import os
import requests
from multiprocessing import Process
import socket
import struct
import zlib
from database import update_mission_data 

DATABASE_PATH = "wildfire_data.db"
SERVER_URL = "http://localhost:8000"
DRONE_ADDRESS = ("127.0.0.1", 5004)  # Localhost UDP port for drone in mode 2
UDP_PORT = 5005  # Port for UDP communication in debug mode (2)

TEST_PACKET_ID = 9999
TEST_PACKET = {
    "pac_id": TEST_PACKET_ID,
    "gps_data": [39.5296, -119.8138],
    "alt": 1500,
    "high_temp": 500,
    "low_temp": 300,
    "time_stamp": 1740990645.9
}

import json
import random
from datetime import datetime, timedelta


def generate_test_data(name, center_lat, center_lon, num_points=1):
    packets = []

    for _ in range(num_points):
        lat = center_lat + random.uniform(-0.01, 0.01)
        lon = center_lon + random.uniform(-0.01, 0.01)
        alt = random.uniform(500, 1500)
        high_temp = random.uniform(300, 650)
        low_temp = random.uniform(100, 399)

        packet = {
            "name": name,
            "pac_id": random.randint(1000, 9999),
            "gps_data": [lat, lon],
            "alt": alt,
            "high_temp": high_temp,
            "low_temp": low_temp,
            "time_stamp": time.time_ns(),
        }
        print(packet)
        return packet

def send_packet_through_main(packet):
        """Send the test packet through main.py and ensure it's added to the database."""
        
        # Check if the packet already exists
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wildfires WHERE pac_id = ?", (packet["pac_id"],))
        existing_packet = cursor.fetchone()
        conn.close()

        if existing_packet:
            print("⚠ Test packet already exists in database. Skipping re-sending.")
            return

        payload = struct.pack(
            '<IffIhhq', 
            int(packet["pac_id"]),       
            float(packet["gps_data"][0]),  
            float(packet["gps_data"][1]),  
            int(packet["alt"]),         
            int(packet["high_temp"]),   
            int(packet["low_temp"]),    
            int(packet["time_stamp"])  
        )
        checksum = zlib.crc32(payload)
        serialized_packet = payload + struct.pack('<I', checksum)

        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.sendto(serialized_packet, ("127.0.0.1", UDP_PORT))
            print(f"✅ Sent test packet to UDP port {UDP_PORT}")
        except socket.error as e:
            print(f"❌ Error sending test packet to UDP: {e}")
        finally:
            udp_socket.close()

def sendTestPackets():
    packet = generate_test_data("New Data Fire", 39.5296, -119.8138)
    send_packet_through_main(packet)
    time.sleep(2)

if __name__ == "__main__":
    while True:
        sendTestPackets()
