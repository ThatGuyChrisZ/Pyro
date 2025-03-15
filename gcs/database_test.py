import unittest
import requests
import time
import json

BASE_URL = "http://localhost:8000"

class TestServerDatabaseIntegration(unittest.TestCase):

    # Test if the server correctly receives wildfire data and stores it in the database.
    def test_add_packet_and_fetch_data(self):
        

        # Sample data
        packet_data = {
            "pac_id": 456,
            "gps_data": [39.5299, 119.8143],  
            "alt": 200.0,
            "high_temp": 90.3,
            "low_temp": 50.1
        }

        response = requests.post(f"{BASE_URL}/add_packet", json=packet_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Packet added successfully", response.json().get("message", ""))

        time.sleep(1)

        response = requests.get(f"{BASE_URL}/get_database", params={"fire_name": "New Data Fire"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)

        # Check that data is same as sample data
        last_entry = data[-1]
        self.assertEqual(last_entry["name"], "New Data Fire")
        self.assertAlmostEqual(last_entry["latitude"], 39.5299, places=4)
        self.assertAlmostEqual(last_entry["longitude"], 119.8143, places=4)
        self.assertEqual(last_entry["high_temp"], 90.3)
        self.assertEqual(last_entry["low_temp"], 50.1)

if __name__ == "__main__":
    unittest.main()
