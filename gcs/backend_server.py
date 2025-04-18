from pymavlink import mavutil
import time
import json
import sqlite3
import multiprocessing as mp
from multiprocessing import Manager
from database import init_db, process_packet, sync_to_firebase, update_mission_data

# This function is referenced but not directly used in our current backend.
def recursive_listen(QGroundControl):
    QGroundControl.wait_heartbeat()
    Attitude = QGroundControl.recv_match(type='ATTITUDE', blocking=True)
    Altitude = QGroundControl.recv_match(type='ALTITUDE', blocking=True)
    Heading = QGroundControl.recv_match(type='VFR_HUD', blocking=True)
    GPS = QGroundControl.recv_match(type='GPS_RAW_INT', blocking=True)
    print("Pitch: ", Attitude.pitch)
    print("Roll:", Attitude.roll)
    print("Yaw:", Attitude.yaw)
    print("Altitude", Altitude.altitude_amsl)
    print("Heading: ", Heading.heading)
    print("Ground Speed: ", Heading.groundspeed)
    print("GPS lat: ", GPS.lat)
    print("GPS lon: ", GPS.lon)
    print("GPS Satellites: ", GPS.satellites_visible)
    new_time = time.time_ns()
    print("Time_Stamp", new_time)
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
            new_time = time.time_ns()
            export = {
                "heading": Heading.heading,
                "speed": Heading.groundspeed,
                "altitude": Altitude.altitude_amsl,
                "latitude": GPS.lat,
                "longitude": GPS.lon,
                "time_stamp": new_time
            }
            print(export)
            update_mission_data(export)

            output.put(export)
            enabled = 1

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

def delayed_sync():
    """Delay Firebase sync to ensure all data is processed first."""
    time.sleep(2)
    sync_to_firebase()

if __name__ == "__main__":
    # Initialize the database
    init_db()
    
    # Optionally import test packets
    import_packets_from_file('test_packets.txt')
    
    # Start the avionics integration process
    q1 = mp.Queue()
    p1 = mp.Process(target=avionics_integration, args=(q1,))
    p1.start()
    
    try:
        while True:
            if not q1.empty():
                data = q1.get()
                print("Received data from avionics:", data)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down backend server.")
        p1.terminate()
