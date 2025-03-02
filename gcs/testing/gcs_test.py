import unittest
import sqlite3
import time
import os
import struct
import zlib
import serial
import requests
from multiprocessing import Process

DATABASE_PATH = "wildfire_data.db"
SERVER_URL = "http://localhost:8000"

# Test Packet Data
TEST_PACKET_ID = 9999
TEST_PACKET = {
    "pac_id": TEST_PACKET_ID,
    "gps_data": [39.5296, -119.8138],
    "alt": 1500,
    "high_temp": 500,
    "low_temp": 300,
}


class TestGCSSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_process = Process(target=os.system, args=("python main_for_testing.py",))
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

        # Wait for main_for_testing.py to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            if cls.is_process_running("main_for_testing.py"):
                print("✅ main_for_testing.py is running.")
                break
            time.sleep(1)
        
        if not cls.is_process_running("main_for_testing.py"):
            raise RuntimeError("❌ main_for_testing.py is NOT running. Ensure GCS UI has started it.")


    @classmethod
    def tearDownClass(cls):
        cls.main_process.terminate()
        cls.server_process.terminate()

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wildfires WHERE pac_id = ?", (TEST_PACKET_ID,))
        conn.commit()
        conn.close()

    @staticmethod
    def is_process_running(target_script):
        import psutil
        for process in psutil.process_iter(attrs=["pid", "cmdline"]):
            cmdline = process.info.get("cmdline", [])
            if cmdline and any(target_script in arg for arg in cmdline):
                return True
        return False


    def test_send_packet_through_main(self):

        payload = struct.pack(
            '<IffIhh',
            TEST_PACKET["pac_id"],
            TEST_PACKET["gps_data"][0],
            TEST_PACKET["gps_data"][1],
            TEST_PACKET["alt"],
            TEST_PACKET["high_temp"],
            TEST_PACKET["low_temp"],
        )
        checksum = zlib.crc32(payload)
        serialized_packet = payload + struct.pack('<I', checksum)

        try:
            with serial.serial_for_url("loop://", 57600, timeout=5) as ser:
                print("Sending test packet to virtual serial port...")
                ser.write(serialized_packet)
                ser.flush()
                time.sleep(1)

        except serial.SerialException as e:
            self.fail(f"❌ Error sending test packet to virtual serial: {e}")

        time.sleep(2)

        # Check database for stored packet
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wildfires WHERE pac_id = ?", (TEST_PACKET_ID,))
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result, "❌ Test packet was not stored in the database.")

if __name__ == "__main__":
    unittest.main()