import time
import struct
import zlib
import socket
import sqlite3
import unittest
import requests
import serial
import os
from multiprocessing import Process

# ------------------- #
# GLOBAL VARIABLES   #
# ------------------- #
DATABASE_PATH = "wildfire_data.db"
SERVER_URL = "http://localhost:8000"
DRONE_ADDRESS = ("127.0.0.1", 5004)
UDP_PORT = 5005  # Debug UDP port for GCS

# ------------------- #
# TEST PACKET DATA   #
# ------------------- #
TEST_PACKET_ID = 6666
TEST_PACKET = {
    "pac_id": TEST_PACKET_ID,
    "gps_data": [39.5296, -119.8138],
    "alt": 1500,
    "high_temp": 500,
    "low_temp": 300,
    "time_stamp": 100000,
    "session_id": "738479814012"
}

class TestGCSSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start main.py and frontend_server.py, wait until they respond."""
        cls.main_process = Process(
            target=os.system,
            args=("python main.py --mode 2",)
        )
        cls.server_process = Process(
            target=os.system,
            args=("python frontend_server.py",)
        )
        cls.main_process.start()
        cls.server_process.start()

        # wait for frontend_server
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                resp = requests.get(f"{SERVER_URL}/wildfire_markers", timeout=2)
                if resp.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                time.sleep(1)

        # wait for main.py
        start_time = time.time()
        while time.time() - start_time < timeout:
            if cls.is_process_running("main.py"):
                break
            time.sleep(1)
        if not cls.is_process_running("main.py"):
            raise RuntimeError("main.py did not start; check GCS UI launch.")

    @classmethod
    def tearDownClass(cls):
        """Terminate processes and clean up test data from the database."""
        cls.main_process.terminate()
        cls.server_process.terminate()

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM wildfires WHERE pac_id = ?", (TEST_PACKET_ID,)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def is_process_running(target_script):
        """Return True if any running process cmdline contains target_script."""
        import psutil
        for proc in psutil.process_iter(attrs=["cmdline"]):
            cmd = proc.info.get("cmdline") or []
            if any(target_script in part for part in cmd):
                return True
        return False

    def test_send_packet_through_main(self):
        """Pack and send a UDP packet, verifying no exceptions are raised."""
        session_bytes = TEST_PACKET["session_id"].encode('ascii')
        if len(session_bytes) < 12:
            session_bytes = session_bytes.ljust(12, b'\x00')
        else:
            session_bytes = session_bytes[:12]

        # Pack fields and checksum
        payload = struct.pack(
            '<IffIhhq12s',
            TEST_PACKET["pac_id"],
            TEST_PACKET["gps_data"][0],
            TEST_PACKET["gps_data"][1],
            TEST_PACKET["alt"],
            TEST_PACKET["high_temp"],
            TEST_PACKET["low_temp"],
            TEST_PACKET["time_stamp"],
            session_bytes
        )
        checksum = zlib.crc32(payload)
        packet = payload + struct.pack('<I', checksum)

        # Send via UDP
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_sock.sendto(packet, ("127.0.0.1", UDP_PORT))
        except socket.error as e:
            self.fail(f"Failed to send UDP packet: {e}")
                                                           #
if __name__ == '__main__':
    unittest.main()