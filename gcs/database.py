import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
import pandas as pd
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


def process_packet(packet, name, status):
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
                name, pac_id, latitude, longitude, alt, high_temp, low_temp, status, date_received, time_received
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status, date_received, time_received)
        )
        conn.commit()
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
            SELECT name, 
                   AVG(latitude) as latitude, 
                   AVG(longitude) as longitude,
                   MIN(latitude) as min_latitude, 
                   MAX(latitude) as max_latitude,
                   MIN(longitude) as min_longitude, 
                   MAX(longitude) as max_longitude,
                   MAX(date_received) as last_date_received,
                   MAX(time_received) as last_time_received
            FROM wildfires
            WHERE status = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY name
        '''
        
        cursor.execute(query, (status,))
        results = cursor.fetchall()
        
        earth_radius_km = 6371.0  # Earth's radius in kilometers
        fire_list = []
        
        for row in results:
            name, latitude, longitude, min_lat, max_lat, min_lon, max_lon, last_date, last_time = row
            
            # Convert degrees to radians for size calculation
            min_lat, max_lat, min_lon, max_lon = map(math.radians, (min_lat, max_lat, min_lon, max_lon))
            
            # Approximate area using the spherical Earth formula
            lat_diff = max_lat - min_lat
            lon_diff = max_lon - min_lon
            size_km2 = (earth_radius_km**2) * abs(math.sin(lat_diff) * lon_diff)
            
            fire_list.append({
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "size": round(size_km2, 2),
                "last_date_received": last_date,
                "last_time_received": last_time
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