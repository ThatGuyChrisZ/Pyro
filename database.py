import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
import pandas as pd

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
            status REAL
        )
        """
    )
    conn.commit()
    conn.close()

def insert_wildfire_data(name: str, latitude: float, longitude: float, high_temp: float, low_temp: float, date: str, time: str, status: str = "active"):
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO wildfires (name, latitude, longitude, high_temp, low_temp, date, time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, latitude, longitude, high_temp, low_temp, date, time, status))
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

        conn = sqlite3.connect("wildfire_data.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO wildfires (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, pac_id, latitude, longitude, alt, high_temp, low_temp, status)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error processing packet: {e}")


def fetch_wildfire_data(name: Optional[str] = None, date: Optional[str] = None, time: Optional[str] = None) -> List[Tuple]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = 'SELECT * FROM wildfires WHERE 1=1'
    params = []
    if name:
        query += ' AND name = ?'
        params.append(name)
    if date:
        query += ' AND date = ?'
        params.append(date)
    if time:
        query += ' AND time = ?'
        params.append(time)
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


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

    required_columns = {'name', 'latitude', 'longitude', 'high_temp', 'low_temp', 'date', 'time', 'status'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        print(f"Error: Missing required columns: {', '.join(missing_columns)}")
        return

    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()

    try:
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO wildfires (name, latitude, longitude, high_temp, low_temp, date, time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['name'], 
                row['latitude'],
                row['longitude'],
                row['high_temp'],
                row['low_temp'],
                row['date'],
                row['time'],
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
            SELECT name, AVG(latitude) as latitude, AVG(longitude) as longitude
            FROM wildfires
            WHERE status = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY name
        '''
        
        cursor.execute(query, (status,))
        results = cursor.fetchall()
        
        fire_list = [{"name": row[0], "latitude": row[1], "longitude": row[2]} for row in results]
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        fire_list = []
    finally:
        conn.close()
    
    return fire_list


def fetch_heatmap_data(name: str) -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = 'SELECT latitude, longitude, high_temp, low_temp FROM wildfires WHERE name = ?'
    cursor.execute(query, (name,))
    results = cursor.fetchall()
    conn.close()
    return [
        {"latitude": row[0], "longitude": row[1], "high_temp": row[2], "low_temp": row[3]}
        for row in results
    ]


def fetch_all_heatmap_data() -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = 'SELECT latitude, longitude, high_temp, low_temp FROM wildfires'
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [
        {"latitude": row[0], "longitude": row[1], "high_temp": row[2], "low_temp": row[3]}
        for row in results
    ]