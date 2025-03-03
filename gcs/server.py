from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json
import sqlite3
import multiprocessing as mp
import pandas as pd
from pymavlink import mavutil
import time
import math
import threading


from database import (
    init_db,
    process_packet,
    fetch_fire_list,
    fetch_heatmap_data,
    fetch_all_heatmap_data,
    sync_to_firebase,
    update_mission_data
)

# Not being used, but referenced
def recursive_listen(QGroundControl):
    QGroundControl.wait_heartbeat()
    Attitude = QGroundControl.recv_match(type='ATTITUDE', blocking=True)
    Altitude = QGroundControl.recv_match(type='ALTITUDE', blocking=True)
    Heading = QGroundControl.recv_match(type='VFR_HUD', blocking=True)
    GPS = QGroundControl.recv_match(type='GPS_RAW_INT', blocking=True)
    #GPS_RAW_INT
    mailbox = QGroundControl.messages.keys()
    enable = 1
    if enable == 2:
        for mail in mailbox:
            print("____________________________________")
            print(mail)
    
    if enable == 1:
        print("_______________________________")
        print("Pitch: ", Attitude.pitch)
        print("Roll:", Attitude.roll)
        print("Yaw:", Attitude.yaw)
        print("Altitude",Altitude.altitude_amsl)
        print("Heading: ",Heading.heading)
        print("Ground Speed: ",Heading.groundspeed)
        print("GPS lat: ", GPS.lat)
        print("GPS lon: ", GPS.lon)
        print("GPS Satelites: ", GPS.satellites_visible)
        new_time = time.time()
        local_time = time.localtime(new_time)
        rounded_time = round(float(new_time),1)
        print("Time_Stamp", rounded_time)
        
        
    recursive_listen(QGroundControl)

def avionics_integration(output):
    QGroundControl = mavutil.mavlink_connection('udpin:localhost:14445')
    enabled = 1
    while True:
        
        if enabled == 1:
            enabled = 0
            QGroundControl.wait_heartbeat()
            Attitude = QGroundControl.recv_match(type='ATTITUDE', blocking=True)
            Altitude = QGroundControl.recv_match(type='ALTITUDE', blocking=True)
            Heading = QGroundControl.recv_match(type='VFR_HUD', blocking=True)
            GPS = QGroundControl.recv_match(type='GPS_RAW_INT', blocking=True)
            Ground_speed = QGroundControl.recv_match(type='VFR_HUD', blocking=True)
            #GPS_RAW_INTs
            mailbox = QGroundControl.messages.keys()
            new_time = time.time()
            local_time = time.localtime(new_time)
            rounded_time = round(float(new_time),1)

            export = {
                "heading": Heading.heading,
                "speed": Heading.groundspeed,
                "altitude": Altitude.altitude_amsl,
                "latitude": GPS.lat,
                "longitude": GPS.lon,
                "time_stamp": rounded_time
            }
            
            print(export)
            update_mission_data(export)

            #Re enable loop
            output.put(export)
            enabled = 1

# used for test data, reads packets as lines in txt file
def import_packets_from_file(file_path):
    """Reads a text file and processes each row as a packet."""
    try:
        with open(file_path, 'r') as file:
            for line in file:
                try:
                    packet_data = json.loads(line.strip())
                    name = packet_data.get("name", "Unnamed Fire")
                    process_packet(packet_data, name, "active")
                except json.JSONDecodeError as e:
                    print(f"Error decoding packet: {e}")
                except Exception as e:
                    print(f"Error processing packet: {e}")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error reading file: {e}")

class NavigationHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        if parsed_path.path == "/wildfire_list":
            filter_type = query_params.get("filter", ["active"])[0]
            fire_data = fetch_fire_list(filter_type)
            self._send_json_response(fire_data)

        elif parsed_path.path == "/heatmap_data":
            name = query_params.get("name", [None])[0]
            date = query_params.get("date", [None])[0]
            time = query_params.get("time", [None])[0]

            if name:
                heatmap_data = fetch_heatmap_data(name, date, time)
            else:
                heatmap_data = fetch_all_heatmap_data()

            self._send_json_response(heatmap_data)

        elif parsed_path.path == "/wildfire_markers":
            filter_type = query_params.get("filter", ["active"])[0]
            wildfire_data = fetch_fire_list(filter_type)
            self._send_json_response(wildfire_data)

        elif parsed_path.path == "/get_database":
            try:
                fire_name = query_params.get("fire_name", [None])[0]

                conn = sqlite3.connect("wildfire_data.db")
                if fire_name:
                    # Fetch data from the 'wildfires' table for the selected fire
                    query = "SELECT * FROM wildfires WHERE name = ?"
                    df = pd.read_sql_query(query, conn, params=(fire_name,))
                else:
                    # Fetch data from the 'wildfire_status' table
                    query = "SELECT * FROM wildfire_status"
                    df = pd.read_sql_query(query, conn)

                conn.close()
                data = df.to_dict(orient="records")
                self._send_json_response(data)
            except Exception as e:
                self._send_error_response(str(e))

        elif parsed_path.path == "/download_csv":
            try:
                conn = sqlite3.connect("wildfire_data.db")
                df = pd.read_sql_query("SELECT * FROM wildfires", conn)
                conn.close()
                csv_path = "wildfire_data.csv"
                df.to_csv(csv_path, index=False)

                self.send_response(200)
                self.send_header("Content-Disposition", f"attachment; filename={csv_path}")
                self.send_header("Content-type", "text/csv")
                self.end_headers()
                with open(csv_path, "rb") as file:
                    self.wfile.write(file.read())
            except Exception as e:
                self._send_error_response(str(e))

        elif parsed_path.path == "/sync_firebase":
            """Manually trigger Firebase sync for any pending data."""
            sync_to_firebase()
            self._send_json_response({"message": "Firebase sync initiated."})

        else:
            super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/add_packet":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                packet_data = json.loads(post_data)
                name = "New Data Fire"
                pac_id = packet_data.get("pac_id", -1)  # Default to -1 if missing
                gps_data = packet_data.get("gps_data", [0.0, 0.0])
                alt = packet_data.get("alt", 0.0)
                high_temp = packet_data.get("high_temp", 0.0)
                low_temp = packet_data.get("low_temp", 0.0)
                time_stamp = packet_data.get("time_stamp", 0.0)

                packet = {
                    "pac_id": pac_id,
                    "gps_data": gps_data,
                    "alt": alt,
                    "high_temp": high_temp,
                    "low_temp": low_temp,
                    "time_stamp": time_stamp
                }

                process_packet(packet, name, "pending")

                self._send_json_response({"message": "Packet added and sync initiated."})
            except Exception as e:
                self._send_error_response(f"Failed to process packet: {str(e)}")

    def _send_json_response(self, data):
        """Send a JSON response."""
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error_response(self, error_message):
        """Send an error response in JSON format."""
        self.send_response(500)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": error_message}).encode())

def delayed_sync():
    """Delay Firebase sync to ensure all data is processed first."""
    time.sleep(2)  # ✅ Wait for mission data updates
    sync_to_firebase()

# Run Server
if __name__ == "__main__":
    # Initialization
    init_db()
    import_packets_from_file('test_packets.txt')

    # Start Avionics Process
    q1 = mp.Queue()
    p1 = mp.Process(target=avionics_integration, args=(q1,))
    p1.start()
    
    # Start Server
    host_name = "localhost"
    port_number = 8000
    server = HTTPServer((host_name, port_number), NavigationHandler)
    print(f"Server running at http://{host_name}:{port_number}/pyro")

    server.serve_forever()