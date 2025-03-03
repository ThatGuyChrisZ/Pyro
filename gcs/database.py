import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
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
    """Initialize the local SQLite database with WAL mode and new sync_status column."""
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
            time_collected REAL,
            heading REAL,
            speed REAL
        )
        """
    )
    
    init_wildfire_status_db()
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
            "time_collected": row[12],
            "heading": row[13],
            "speed": row[14]
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
    """Process a new wildfire packet, store it in SQLite, and attempt Firebase sync."""
    try:
        pac_id = packet.get("pac_id", -1)
        gps_data = packet.get("gps_data", [0.0, 0.0])
        latitude, longitude = gps_data[0], gps_data[1]
        alt = packet.get("alt", 0.0)
        high_temp = packet.get("high_temp", 0.0)
        low_temp = packet.get("low_temp", 0.0)
        time_collected = packet.get("time_collected", 0.0)
        heading = 0
        speed = 0

        now = datetime.now()
        date_received = now.strftime("%Y-%m-%d")
        time_received = now.strftime("%H:%M:%S")

        conn = sqlite3.connect("wildfire_data.db", timeout=5)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO wildfires (
                name, pac_id, latitude, longitude, alt, high_temp, low_temp, 
                status, date_received, time_received, sync_status, time_collected,
                heading, speed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status, date_received, time_received, "pending", time_collected, heading, speed)
        )

        conn.commit()
        conn.close()

        update_fire_status(name, latitude, longitude, high_temp, low_temp, alt)

        # Run Firebase sync in parallel thread
        sync_thread = Thread(target=sync_to_firebase)
        sync_thread.start()

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
        SELECT latitude, longitude, high_temp, low_temp 
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
        {"latitude": row[0], "longitude": row[1], "high_temp": row[2], "low_temp": row[3]}
        for row in results
    ]

def fetch_all_heatmap_data() -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = '''
        SELECT latitude, longitude, high_temp, low_temp, date_received, time_received 
        FROM wildfires
    '''
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "latitude": row[0],
            "longitude": row[1],
            "high_temp": row[2],
            "low_temp": row[3],
            "date_received": row[4],
            "time_received": row[5]
        } for row in results
    ]

# Wildfire Status Db
def init_wildfire_status_db():
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wildfire_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            location TEXT,
            size REAL DEFAULT 0.0,
            intensity REAL DEFAULT 0.0,
            alt_avg REAL DEFAULT 0.0,
            num_data_points INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            max_temp REAL DEFAULT 0.0,
            min_temp REAL DEFAULT 0.0,
            lat_range REAL DEFAULT 0.0,
            lon_range REAL DEFAULT 0.0,
            avg_latitude REAL DEFAULT 0.0,
            avg_longitude REAL DEFAULT 0.0,
            first_date_received STRING,
            first_time_received STRING,
            last_updated STRING
        )
        """
    )
    conn.commit()
    conn.close()

def update_fire_status(name: str, latitude: float, longitude: float, high_temp: float, low_temp: float, altitude: float):
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wildfire_status WHERE name = ?", (name,))
    fire = cursor.fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if fire:
        fire_id, _, location, size, intensity, alt_avg, num_data_points, status, max_temp, min_temp, lat_range, lon_range, avg_lat, avg_lon, first_date, first_time, _ = fire

        # Calculate new stats
        new_num_points = num_data_points + 1
        new_intensity = ((intensity * num_data_points) + (high_temp + low_temp) / 2) / new_num_points
        new_max_temp = max(max_temp, high_temp)
        new_min_temp = min(min_temp, low_temp)
        new_lat_range = max(lat_range, abs(latitude))
        new_lon_range = max(lon_range, abs(longitude))
        new_alt_avg = ((alt_avg * num_data_points) + altitude) / new_num_points
        new_avg_lat = ((avg_lat * num_data_points) + latitude) / new_num_points
        new_avg_lon = ((avg_lon * num_data_points) + longitude) / new_num_points
        
        lat_diff_km = new_lat_range * 111.32 
        lon_diff_km = new_lon_range * 111.32 * math.cos(math.radians(new_avg_lat))
        new_size = abs(lat_diff_km * lon_diff_km)

        cursor.execute(
            """
            UPDATE wildfire_status
            SET size = ?, intensity = ?, alt_avg = ?, num_data_points = ?,
                max_temp = ?, min_temp = ?, lat_range = ?, lon_range = ?,
                avg_latitude = ?, avg_longitude = ?, last_updated = ?
            WHERE name = ?
            """,
            (new_size, new_intensity, new_alt_avg, new_num_points, new_max_temp, new_min_temp,
             new_lat_range, new_lon_range, new_avg_lat, new_avg_lon, now, name)
        )
    else:
        # Insert new fire
        location = get_nearest_city(latitude, longitude)
        size = 0.0 
        intensity = (high_temp + low_temp) / 2
        alt_avg = altitude 
        lat_range = latitude
        lon_range = longitude
        num_data_points = 1
        first_date = now.split(" ")[0]
        first_time = now.split(" ")[1]
        avg_lat = latitude
        avg_lon = longitude

        cursor.execute(
            """
            INSERT INTO wildfire_status (
                name, location, size, intensity, alt_avg, num_data_points, status,
                max_temp, min_temp, lat_range, lon_range, avg_latitude, avg_longitude,
                first_date_received, first_time_received, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, location, size, intensity, alt_avg, num_data_points, "active",
             high_temp, low_temp, lat_range, lon_range, avg_lat, avg_lon, first_date, first_time, now)
        )

    conn.commit()
    conn.close()

def get_nearest_city(latitude: float, longitude: float) -> str:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=10"
        
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
    
def update_mission_data(mission_time, gps_data, alt, heading, speed):
    # Ensure the table has the needed columns.
    
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    try:
        query = """
            UPDATE wildfires
            SET latitude = ?,
                longitude = ?,
                alt = ?,
                heading = ?,
                speed = ?,
                sync_status = 'pending'
            WHERE time_collected = ?
        """
        cursor.execute(query, (gps_data[0], gps_data[1], alt, heading, speed, mission_time))
        conn.commit()
        if cursor.rowcount == 0:
            print("No wildfire record found matching the given time.")
        else:
            print("Wildfire record updated with mission data.")
    except Exception as e:
        print(f"Error updating mission data: {e}")
    finally:
        conn.close()
