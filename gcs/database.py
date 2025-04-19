import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
import requests
import math
import firebase_admin
from firebase_admin import credentials, db
import time
from threading import Thread

# Firebase Config
FIREBASE_CREDENTIALS_PATH = "firebase_credentials.json"
FIREBASE_DB_URL = "https://pyro-fire-tracking-default-rtdb.firebaseio.com/"

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

firebase_ref = db.reference("wildfires")

def init_db():
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # sync_status refers to whether data is synced to Firebase
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wildfires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pac_id INTEGER NOT NULL DEFAULT -1,
            latitude REAL,
            longitude REAL,
            alt REAL,
            high_temp REAL,
            low_temp REAL,
            date_received STRING,
            time_received STRING,
            status TEXT DEFAULT 'active',
            sync_status TEXT DEFAULT 'pending', 
            time_stamp REAL,
            heading REAL,
            speed REAL,
            flight_id INTEGER NOT NULL DEFAULT -1,
            session_id STRING
        )
        """
    )
    
    init_wildfire_status_db()
    init_flights_db()
    conn.commit()
    conn.close()

def is_data_in_firebase(name, date_received, time_received):
    """Check if wildfire data exists in Firebase"""
    try:
        existing_data = firebase_ref.child("wildfires").get()

        if isinstance(existing_data, dict):
            for key, fire in existing_data.items():
                if isinstance(fire, dict) and fire.get("name") == name and fire.get("date_received") == date_received and fire.get("time_received") == time_received:
                    return True

        return False

    except Exception as e:
        print(f"⚠ Firebase query failed: {e}")
        return False

def sync_to_firebase():
    """Sync all pending SQLite data to Firebase using batch writes."""
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    # Fetch all unsynced data
    cursor.execute("SELECT * FROM wildfires WHERE sync_status = 'pending'")
    unsynced_data = cursor.fetchall()

    if not unsynced_data:
        print("No new data to sync.")
        return

    print(f"Found {len(unsynced_data)} pending records to sync...")

    batch_data = {}
    ids_to_update = []

    for row in unsynced_data:
        fire_data = {
            "name": row[1],
            "pac_id": row[2],
            "latitude": row[3],
            "longitude": row[4],
            "alt": row[5],
            "high_temp": row[6],
            "low_temp": row[7],
            "date_received": row[8],
            "time_received": row[9],
            "status": row[10],
            "sync_status": row[11],
            "time_stamp": row[12],
            "heading": row[13],
            "speed": row[14],
            "flight_id": row[15],
            "session_id": row[16]
        }

        # Add to batch only if it doesn't already exist in Firebase
        if not is_data_in_firebase(fire_data["name"], fire_data["date_received"], fire_data["time_received"]):
            batch_data[f"wildfires/{row[0]}"] = fire_data 
            ids_to_update.append(row[0])

    if batch_data:
        try:
            firebase_ref.update(batch_data) 
            print(f"Successfully synced {len(batch_data)} records to Firebase.")

            cursor.executemany("UPDATE wildfires SET sync_status = 'synced' WHERE id = ?", [(id,) for id in ids_to_update])
            conn.commit()

        except Exception as e:
            print(f"Failed to sync batch: {e}")

    conn.close()

def process_packet(packet, name, status="active"):
    try:
        ns24h = 24 * 60 * 60 * 1_000_000_000 
        pac_id = packet.get("pac_id", -1)
        session_id = packet.get("session_id", -1)
        flight_id = process_new_flight(name, session_id) or 0
        gps_data = packet.get("gps_data", [0.0, 0.0])
        latitude, longitude = gps_data[0], gps_data[1]
        alt = packet.get("alt", 0.0)
        high_temp = packet.get("high_temp", 0.0)
        low_temp = packet.get("low_temp", 0.0)
        time_stamp = packet.get("time_stamp", time.time_ns() - (1/200) * ns24h)
        heading = 0
        speed = 0

        now = datetime.now()
        date_received = now.strftime("%Y-%m-%d")
        time_received = now.strftime("%H:%M:%S")

        conn = sqlite3.connect("wildfire_data.db", timeout=5)
        cursor = conn.cursor()

        # Check for duplicate packet based on pac_id and time_stamp
        cursor.execute(
            "SELECT COUNT(*) FROM wildfires WHERE pac_id = ? AND time_stamp = ?",
            (pac_id, time_stamp)
        )
        duplicate_count = cursor.fetchone()[0]
        if duplicate_count > 0:
            #print(f"Duplicate packet (pac_id: {pac_id}, time_stamp: {time_stamp}) found. Skipping insertion.")
            conn.close()
            return

        cursor.execute(
            """
            INSERT INTO wildfires (
                name, pac_id, latitude, longitude, alt, high_temp, low_temp, 
                status, date_received, time_received, sync_status, time_stamp,
                heading, speed, flight_id, session_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status,
             date_received, time_received, "pending", time_stamp, heading, speed, flight_id, session_id)
        )

        conn.commit()
        conn.close()

        # update_fire_status(name)
        update_flights(flight_id, session_id, name, "ulog_filename")

        # Run Firebase sync in a parallel thread
        #sync_thread = Thread(target=sync_to_firebase)
        #sync_thread.start()

    except Exception as e:
        print(f"Error processing packet: {e}")


def fetch_fire_list(status: str = "active") -> List[dict]:
    try:
        conn = sqlite3.connect('wildfire_data.db')
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                name, 
                location, 
                size, 
                intensity, 
                alt_avg, 
                num_data_points, 
                max_temp, 
                min_temp, 
                avg_latitude, 
                avg_longitude, 
                first_date_received, 
                first_time_received, 
                last_updated
            FROM wildfire_status
            WHERE status = ?
        '''
        
        cursor.execute(query, (status,))
        results = cursor.fetchall()
        
        fire_list = []
        for row in results:
            fire_list.append({
                "name": row[0],
                "location": row[1],
                "size": round(row[2], 2),
                "intensity": round(row[3], 2),
                "alt_avg": round(row[4], 2),
                "num_data_points": row[5],
                "max_temp": round(row[6], 2),
                "min_temp": round(row[7], 2),
                "avg_latitude": round(row[8], 6),
                "avg_longitude": round(row[9], 6),
                "first_date_received": row[10],
                "first_time_received": row[11],
                "last_updated": row[12],
            })
        
        return fire_list
    except Exception as e:
        print(f"Error fetching fire list: {e}")
        return []
    finally:
        if conn:
            conn.close()


def fetch_heatmap_data(name: str, date: Optional[str] = None, time: Optional[str] = None) -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = '''
        SELECT latitude, longitude, high_temp, low_temp, date_received, time_received, time_stamp, alt
        FROM wildfires 
        WHERE name = ?
    '''
    params = [name]

    if date:
        query += ' AND date_received <= ?'
        params.append(date)
    if time:
        query += ' AND time_received <= ?'
        params.append(time)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [
        {"latitude": row[0], "longitude": row[1], "high_temp": row[2], "low_temp": row[3], "date_received": row[4], "time_received": row[5], "time_stamp": row[6], "altitude": row[7]}
        for row in results
    ]

def fetch_all_heatmap_data() -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = '''
        SELECT latitude, longitude, high_temp, low_temp, date_received, time_received, alt
        FROM wildfires
    '''
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [
        {"latitude": row[0], "longitude": row[1], "high_temp": row[2], "low_temp": row[3], "date_received": row[4], "time_received": row[5], "time_stamp": row[6], "altitude": row[7]}
        for row in results
    ]

# Wildfire Status Db
MIN_TEMP_THRESHOLD = 200

def init_wildfire_status_db():
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wildfire_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, 
            location TEXT,
            size REAL DEFAULT 0.0,
            intensity REAL DEFAULT 0.0,
            alt_avg REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            max_temp REAL DEFAULT 0.0,
            min_temp REAL DEFAULT 0.0,
            avg_latitude REAL DEFAULT 0.0,
            avg_longitude REAL DEFAULT 0.0,
            flights REAL DEFAULT 0.0,
            num_data_points REAL DEFAULT 0.0,
            first_time_stamp REAL, 
            time_stamp REAL,
            last_flight_id INTEGER DEFAULT NULL
        );
        """
    )
    conn.commit()
    conn.close()

# Each record represents an data aggregate update from the past 24 hours
def update_fire_status(name: str):
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    now = time.time_ns()
    ns24h = 24 * 60 * 60 * 1_000_000_000 
    window_start = now - ns24h

    # Data from the past 24 hours
    cursor.execute(
        """
        SELECT latitude, longitude, high_temp, low_temp, alt, flight_id, time_stamp 
        FROM wildfires 
        WHERE name = ? AND time_stamp >= ? AND high_temp >= ?
        """,
        (name, window_start, MIN_TEMP_THRESHOLD)
    )
    rows = cursor.fetchall()
    if not rows:
        print(f"No recent data for fire {name} meeting the threshold.")
        conn.close()
        return

    latitudes = []
    longitudes = []
    intensities = []
    altitudes = []
    high_temps = []
    low_temps = []
    flight_ids = set()
    timestamps = []

    for row in rows:
        lat, lon, high_temp, low_temp, alt, flight_id, ts = row
        latitudes.append(lat)
        longitudes.append(lon)
        intensities.append((high_temp + low_temp) / 2)
        altitudes.append(alt)
        high_temps.append(high_temp)
        low_temps.append(low_temp)
        flight_ids.add(flight_id)
        timestamps.append(ts)

    num_points = len(intensities)
    new_intensity = sum(intensities) / num_points
    new_alt_avg = sum(altitudes) / num_points
    new_avg_lat = sum(latitudes) / num_points
    new_avg_lon = sum(longitudes) / num_points
    new_max_temp = max(high_temps)
    new_min_temp = min(low_temps)
    new_flights = len(flight_ids)
    new_first_time_stamp = min(timestamps)
    new_time_stamp = max(timestamps)
    new_last_flight_id = max(flight_ids)

    # Size Calculation
    max_lat = max(latitudes)
    min_lat = min(latitudes)
    max_lon = max(longitudes)
    min_lon = min(longitudes)
    lat_diff = max_lat - min_lat
    lon_diff = max_lon - min_lon
    avg_lat_for_conv = (max_lat + min_lat) / 2
    lat_diff_km = lat_diff * 111.32
    lon_diff_km = lon_diff * 111.32 * math.cos(math.radians(avg_lat_for_conv))
    new_size = abs(lat_diff_km * lon_diff_km) 

    location = get_nearest_city(new_avg_lat, new_avg_lon)
    
    cursor.execute(
        """
        INSERT INTO wildfire_status (
            name, location, size, intensity, alt_avg,
            avg_latitude, avg_longitude, flights, num_data_points,
            first_time_stamp, time_stamp, status,
            max_temp, min_temp, last_flight_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, location, new_size, new_intensity, new_alt_avg,
         new_avg_lat, new_avg_lon, new_flights, num_points,
         new_first_time_stamp, new_time_stamp, "active",
         new_max_temp, new_min_temp, new_last_flight_id)
    )

    conn.commit()
    conn.close()

def process_new_flight(name: str, session_id: str):
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    # Check if this session already exists in the flights table
    cursor.execute(
        "SELECT flight_id FROM flights WHERE name = ? AND session_id = ?",
        (name, session_id)
    )
    row = cursor.fetchone()

    if row:
        conn.close()
        return row[0]  # Return existing flight_id

    # Assign new flight_id
    cursor.execute(
        "SELECT MAX(flight_id) FROM flights WHERE name = ?",
        (name,)
    )
    result = cursor.fetchone()
    last_flight_id = result[0] if result and result[0] is not None else 0
    new_flight_id = last_flight_id + 1
    update_fire_status(name)

    # Insert new session/flight mapping
    cursor.execute(
        """
        INSERT INTO flights (flight_id, name, session_id, time_started)
        VALUES (?, ?, ?, ?)
        """,
        (new_flight_id, name, session_id, time.time())
    )

    conn.commit()
    conn.close()

    print(f"New flight session '{session_id}' received for {name}. Assigned flight ID {new_flight_id}.")
    return new_flight_id
    
def get_nearest_city(latitude: float, longitude: float) -> str:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=5"
        response = requests.get(url, headers={"User-Agent": "wildfire-status-app"})
        if response.status_code == 200:
            data = response.json()
            return data.get("address", {}).get("city", "Unknown Location")
        else:
            print(f"Failed to fetch location: {response.status_code}, {response.text}")
            return "Unknown Location"
    except Exception as e:
        print(f"Error getting nearest city: {e}")
        return "Unknown Location"
  
def update_mission_data(export):
    mission_time = export.get("time_stamp")
    gps_lat = export.get("latitude", 0.0) / 1e6
    gps_lon = export.get("longitude", 0.0) / 1e6
    alt = export.get("altitude", 0.0)
    heading = export.get("heading", 0.0)
    speed = export.get("speed", 0.0)

    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    try:
        # Get all wildfire records after this time that don't yet have mission data
        select_query = """
            SELECT id FROM wildfires
            WHERE time_stamp >= ?
              AND (heading IS NULL OR speed IS NULL OR latitude IS NULL OR longitude IS NULL OR alt IS NULL)
            ORDER BY time_stamp ASC
        """
        cursor.execute(select_query, (mission_time,))
        rows_to_update = cursor.fetchall()

        if not rows_to_update:
            print("No wildfire records found to update mission data.")
            return

        update_query = """
            UPDATE wildfires
            SET 
                heading = ?,
                speed = ?,
                latitude = ?,
                longitude = ?,
                alt = ?,
                sync_status = 'pending'
            WHERE id = ?
        """

        for row in rows_to_update: 
            record_id = row[0]
            cursor.execute(update_query, (heading, speed, gps_lat, gps_lon, alt, record_id))

        conn.commit()
        print(f"✅ Updated mission data to {len(rows_to_update)} wildfire records.")

    except Exception as e:
        print(f"❌ Error updating mission data: {e}")
    finally:
        conn.close()


# Flight_id / Ulog Database
def init_flights_db():
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS flights (
            flight_id INTEGER,
            name TEXT,
            session_id STRING,
            ulog_filename TEXT,
            time_started REAL,
            time_ended
        )
        """
    )
    conn.commit()
    conn.close()

import time
import sqlite3

def update_flights(flight_id, session_id, name, ulog_filename):
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM flights WHERE flight_id = ? AND name = ?", (flight_id, name,))
    count = cursor.fetchone()[0]

    if count == 0:
        # Insert new flight with current timestamp
        time_started = time.time_ns()
        cursor.execute(
            """
            INSERT INTO flights (flight_id, name, session_id, ulog_filename, time_started, time_ended)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (flight_id, name, session_id, ulog_filename, time_started, time_started)
        )
        conn.commit()
    else:
        cursor.execute(
            """
            UPDATE flights
            SET time_ended = ?
            WHERE flight_id = ?
            """,
            (time.time_ns(), flight_id)
        )
        conn.commit()
        conn.close()
