import sqlite3
from typing import List, Tuple, Optional
import pandas as pd


# Initialize the database connection
def init_db():
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wildfires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            temperature REAL NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def insert_wildfire_data(name: str, latitude: float, longitude: float, temperature: float, date: str, time: str, status: str = "active"):
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO wildfires (name, latitude, longitude, temperature, date, time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, latitude, longitude, temperature, date, time, status))
    conn.commit()
    conn.close()

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


def import_csv_to_db(csv_file_path: str, status: str = "active"):
    df = pd.read_csv(csv_file_path)

    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO wildfires (name, latitude, longitude, temperature, date, time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['name'], 
            row['latitude'],
            row['longitude'],
            row['temperature'],
            row['date'],
            row['time'],
            row['status']
        ))

    conn.commit()
    conn.close()

    print(f"Data from {csv_file_path} imported successfully")


def fetch_fire_list(status: str = "active") -> List[dict]:
    """
    Fetches a list of wildfires by status (active or past).

    Returns:
        List[Dict]: A list of wildfires with name, latitude, and longitude.
    """
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = '''
        SELECT name, AVG(latitude) as latitude, AVG(longitude) as longitude
        FROM wildfires
        WHERE status = ?
        GROUP BY name
    '''
    cursor.execute(query, (status,))
    results = cursor.fetchall()
    conn.close()
    return [{"name": row[0], "latitude": row[1], "longitude": row[2]} for row in results]

def fetch_heatmap_data(fire_name: str) -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = 'SELECT latitude, longitude, temperature FROM wildfires WHERE name = ?'
    cursor.execute(query, (fire_name,))
    results = cursor.fetchall()
    conn.close()
    return [{"latitude": row[0], "longitude": row[1], "temperature": row[2]} for row in results]

def fetch_all_heatmap_data() -> List[dict]:
    conn = sqlite3.connect('wildfire_data.db')
    cursor = conn.cursor()
    query = 'SELECT latitude, longitude, temperature FROM wildfires'
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return [{"latitude": row[0], "longitude": row[1], "temperature": row[2]} for row in results]