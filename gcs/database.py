import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
import pandas as pd
import requests
import math

def init_db():
    conn = sqlite3.connect("wildfire_data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wildfires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pac_id INTEGER NOT NULL,
            latitude REAL,
            longitude REAL,
            alt REAL,
            high_temp REAL,
            low_temp REAL,
            date_received STRING,
            time_received STRING,
            status REAL
        )
        """
    )
    init_wildfire_status_db()
    conn.commit()
    conn.close()

def insert_wildfire_data(name: str, latitude: float, longitude: float, high_temp: float, low_temp: float, 
                         date_received: str, time_received: str, status: str = "active"):
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO wildfires (
            name, latitude, longitude, high_temp, low_temp, date_received, time_received, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, latitude, longitude, high_temp, low_temp, date_received, time_received, status))
    conn.commit()
    conn.close()

def process_packet(packet, name, status="active"):
    try:
        pac_id = packet.get("pac_id")
        gps_data = packet.get("gps_data", [0.0, 0.0])
        latitude, longitude = gps_data[0], gps_data[1]
        alt = packet.get("alt", 0.0)
        high_temp = packet.get("high_temp", 0.0)
        low_temp = packet.get("low_temp", 0.0)

        # Get current date and time
        now = datetime.now()
        date_received = now.strftime("%Y-%m-%d")
        time_received = now.strftime("%H:%M:%S")

        conn = sqlite3.connect("wildfire_data.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO wildfires (
                name, pac_id, latitude, longitude, alt, high_temp, low_temp, 
                status, date_received, time_received
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status, date_received, time_received)
        )

        conn.commit()

        update_fire_status(name, latitude, longitude, high_temp, low_temp, alt)

        conn.close()
    except Exception as e:
        print(f"Error processing packet: {e}")


def fetch_wildfire_data(name: Optional[str] = None, date: Optional[str] = None, time: Optional[str] = None) -> List[Tuple]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = '''
        SELECT name, latitude, longitude, high_temp, low_temp, status, date_received, time_received 
        FROM wildfires 
        WHERE 1=1
    '''
    params = []
    if name:
        query += ' AND name = ?'
        params.append(name)
    if date:
        query += ' AND date_received = ?'
        params.append(date)
    if time:
        query += ' AND time_received = ?'
        params.append(time)
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "name": row[0],
            "latitude": row[1],
            "longitude": row[2],
            "high_temp": row[3],
            "low_temp": row[4],
            "status": row[5],
            "date_received": row[6],
            "time_received": row[7]
        } for row in results
    ]

#for previous implementation when test data was from a CSV file
def import_csv_to_db(csv_file_path: str, default_status: str = "active"):
    try:
        df = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"Error: File {csv_file_path} not found.")
        return
    except pd.errors.EmptyDataError:
        print(f"Error: File {csv_file_path} is empty.")
        return

    if 'status' not in df.columns:
        df['status'] = default_status

    now = datetime.now()
    if 'date_received' not in df.columns:
        df['date_received'] = now.strftime("%Y-%m-%d")
    if 'time_received' not in df.columns:
        df['time_received'] = now.strftime("%H:%M:%S")

    required_columns = {'name', 'latitude', 'longitude', 'high_temp', 'low_temp', 'date_received', 'time_received', 'status'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        print(f"Error: Missing required columns: {', '.join(missing_columns)}")
        return

    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()

    try:
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO wildfires (name, latitude, longitude, high_temp, low_temp, date_received, time_received, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['name'], 
                row['latitude'],
                row['longitude'],
                row['high_temp'],
                row['low_temp'],
                row['date_received'],
                row['time_received'],
                row['status']
            ))
        conn.commit()
        print(f"Data from {csv_file_path} imported successfully.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        conn.close()


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
    