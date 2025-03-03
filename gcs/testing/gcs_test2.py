import unittest
import sqlite3
import time
import os
import requests
from multiprocessing import Process
import socket
import struct
import zlib
from database import update_mission_data  # Import the function directly

DATABASE_PATH = "wildfire_data.db"
SERVER_URL = "http://localhost:8000"
DRONE_ADDRESS = ("127.0.0.1", 5004)  # Localhost UDP port for drone in mode 2
UDP_PORT = 5005  # Port for UDP communication in debug mode (2)

# Sample Test Mission Data (simulated QGroundControl data)
TEST_MISSION_DATA = [
    {'heading': 113, 'speed': 0.19, 'altitude': 1367.915, 'latitude': 395403690, 'longitude': -1198125921, 'time_stamp': 1740990654.8},
]

# Test Packet Data
TEST_PACKET_ID = 9998
TEST_PACKET = {
    "pac_id": TEST_PACKET_ID,
    "gps_data": [39.5296, -119.8138],
    "alt": 1500,
    "high_temp": 500,
    "low_temp": 300,
    "time_stamp": 1740990654.9
}

class TestMissionDataIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start the GCS server and main process."""
        
        cls.main_process = Process(target=os.system, args=("python main.py --mode 2",))
        cls.server_process = Process(target=os.system, args=("python server.py",))

        cls.main_process.start()
        cls.server_process.start()

        timeout = 10
        start_time = time.time()

        # Wait for server.py to be responsive
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{SERVER_URL}/wildfire_list", timeout=2)
                if response.status_code == 200:
                    print("✅ server.py is running and responsive.")
                    break
            except requests.exceptions.RequestException:
                time.sleep(1)

        # Ensure main.py started
        start_time = time.time()
        while time.time() - start_time < timeout:
            if cls.is_process_running("main.py"):
                print("✅ main.py is running.")
                break
            time.sleep(1)
        
        if not cls.is_process_running("main.py"):
            raise RuntimeError("❌ main.py is NOT running.")

    @classmethod
    def tearDownClass(cls):
        cls.main_process.terminate()
        cls.server_process.terminate()

        #udp_socket.close()

    @staticmethod
    def is_process_running(target_script):
        import psutil
        for process in psutil.process_iter(attrs=["pid", "cmdline"]):
            cmdline = process.info.get("cmdline", [])
            if cmdline and any(target_script in arg for arg in cmdline):
                return True
        return False
    
    def test_send_packet_through_main(self):
        """Send the test packet through main.py and ensure it's added to the database."""
        
        # Check if the packet already exists
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wildfires WHERE pac_id = ?", (TEST_PACKET_ID,))
        existing_packet = cursor.fetchone()
        conn.close()

        if existing_packet:
            print("⚠ Test packet already exists in database. Skipping re-sending.")
            return

        payload = struct.pack(
            '<IffIhhq', 
            int(TEST_PACKET["pac_id"]),       
            float(TEST_PACKET["gps_data"][0]),  
            float(TEST_PACKET["gps_data"][1]),  
            int(TEST_PACKET["alt"]),         
            int(TEST_PACKET["high_temp"]),   
            int(TEST_PACKET["low_temp"]),    
            int(TEST_PACKET["time_stamp"])  
        )
        checksum = zlib.crc32(payload)
        serialized_packet = payload + struct.pack('<I', checksum)

        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.sendto(serialized_packet, ("127.0.0.1", UDP_PORT))
            print(f"✅ Sent test packet to UDP port {UDP_PORT}")
        except socket.error as e:
            print(f"❌ Error sending test packet to UDP: {e}")

        # Retry loop
        for _ in range(5):  # Retry up to 5 times
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wildfires WHERE pac_id = ?", (TEST_PACKET_ID,))
            result = cursor.fetchone()
            conn.close()

            if result:
                print("✅ Test packet stored in database:", result)
                break
            time.sleep(1)

        self.assertIsNotNone(result, "❌ Test packet was not stored in the database.")



    def test_update_mission_data(self):
        self.test_send_packet_through_main() 

        for mission_entry in TEST_MISSION_DATA:
            print(f"✅ Injecting mission data: {mission_entry}")
            update_mission_data(mission_entry)  # Call update_mission_data directly

        time.sleep(2)

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT latitude, longitude, heading, speed FROM wildfires WHERE heading = ?", 
                       (TEST_MISSION_DATA[0]["heading"],))
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result, "❌ Mission data not stored in the database.")
        print("✅ Mission data stored in database:", result)

if __name__ == "__main__":
    unittest.main()
