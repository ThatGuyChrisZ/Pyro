import unittest
import time
import requests
from multiprocessing import Process

DATABASE_PATH = "wildfire_data.db"
SERVER_URL = "http://localhost:8000"

class TestGCSUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_check_if_running(cls)
    
    def test_check_if_running(cls):
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

    @staticmethod
    def is_process_running(target_script):
        import psutil
        for process in psutil.process_iter(attrs=["pid", "cmdline"]):
            cmdline = process.info.get("cmdline", [])
            if cmdline and any(target_script in arg for arg in cmdline):
                return True
        return False
    

if __name__ == "__main__":
    unittest.main()