import os
import json
import sqlite3
import logging
import pandas as pd
from datetime import datetime
import tornado.ioloop
import tornado.web
import tornado.websocket
from pymavlink import mavutil
import time
import multiprocessing as mp
from tornado.options import define, options, parse_command_line
from urllib.parse import parse_qs
from database import init_db, process_packet, update_mission_data, fetch_heatmap_data, fetch_all_heatmap_data, sync_to_firebase, update_fire_status

# Command Line Arguments
define("port", default=8000, help="Run on the given port", type=int)
define("debug", default=False, help="Run in debug mode", type=bool)
define("db_path", default="wildfire_data.db", help="Path to SQLite database", type=str)

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        
    def prepare(self):
        self.db = sqlite3.connect(options.db_path)
        self.db.row_factory = sqlite3.Row
        
    def on_finish(self):
        if hasattr(self, 'db'):
            self.db.close()

class MainHandler(BaseHandler):
    def get(self):
        self.redirect("/fires")

# Navigation handlers
class FiresHandler(BaseHandler):
    def get(self):
        self.render("fires.html")

class FlightsHandler(BaseHandler):
    def get(self):
        self.render("flights.html")

class DataHandler(BaseHandler):
    def get(self):
        self.render("data.html")

class AboutHandler(BaseHandler):
    def get(self):
        self.render("about.html")

# API Endpoint Handlers

class HeatmapDataHandler(BaseHandler):
    def get(self):
        name = self.get_argument("name", None)
        date = self.get_argument("date", None)
        time_param = self.get_argument("time", None)
        
        if name:
            heatmap_data = fetch_heatmap_data(name, date, time_param)
        else:
            heatmap_data = fetch_all_heatmap_data()
            
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(heatmap_data))

class WildfireMarkersHandler(BaseHandler):
    def get(self):
        filter_type = self.get_argument("filter", "active")
        cursor = self.db.cursor()

        query = """
            SELECT 
                ws.id,
                ws.name, 
                ws.location,
                ws.size,
                ws.intensity,
                ws.alt_avg,
                ws.status,
                ws.max_temp,
                ws.min_temp,
                ws.avg_latitude,
                ws.avg_longitude,
                ws.flights,
                ws.num_data_points,
                ws.first_time_stamp, 
                ws.time_stamp,
                ws.last_flight_id
            FROM wildfire_status ws
            JOIN (
                SELECT name, MAX(time_stamp) AS max_time_stamp
                FROM wildfire_status
                WHERE 1=1
        """

        if filter_type == "active":
            query += " AND status = 'active'"
        elif filter_type == "archived":
            query += " AND status = 'archived'"

        query += """
                GROUP BY name
            ) latest ON ws.name = latest.name AND ws.time_stamp = latest.max_time_stamp
            ORDER BY ws.time_stamp DESC
        """

        cursor.execute(query)
        fires = [dict(row) for row in cursor.fetchall()]

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(fires))

class DatabaseQueryHandler(BaseHandler):
    def get(self):
        try:
            fire_name = self.get_argument("fire_name", None)
            table = self.get_argument("table", "wildfire_status")
            conn = sqlite3.connect(options.db_path)

            if table not in ["wildfire_status", "wildfires"]:
                raise ValueError("Invalid table name")
                
            if table == "wildfire_status":
                if fire_name:
                    # Return only the most recent record for the specified fire
                    query = """
                        SELECT *
                        FROM wildfire_status
                        WHERE name = ?
                        ORDER BY time_stamp DESC
                        LIMIT 1
                    """
                    df = pd.read_sql_query(query, conn, params=(fire_name,))
                else:
                    # Return only the most recent record for each fire name.
                    query = """
                        SELECT t.*
                        FROM wildfire_status t
                        JOIN (
                        SELECT 
                            name, 
                            MAX(time_stamp) AS max_time_stamp,
                            MAX(id) AS max_id
                        FROM wildfire_status
                        GROUP BY name
                        ) latest
                        ON t.name = latest.name 
                        AND t.time_stamp = latest.max_time_stamp
                        AND t.id = latest.max_id
                    """
                    df = pd.read_sql_query(query, conn)
            elif table == "wildfires":
                if fire_name:
                    query = "SELECT * FROM wildfires WHERE name = ?"
                    df = pd.read_sql_query(query, conn, params=(fire_name,))
                else:
                    query = "SELECT * FROM wildfires"
                    df = pd.read_sql_query(query, conn)

            conn.close()
            data = df.to_dict(orient="records")

            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(data))

        except Exception as e:
            self.set_status(500)
            self.write(json.dumps({"error": str(e)}))

class DownloadCSVHandler(BaseHandler):
    def get(self):
        try:
            conn = sqlite3.connect(options.db_path)
            df = pd.read_sql_query("SELECT * FROM wildfires", conn)
            conn.close()
            
            csv_path = "wildfire_data.csv"
            df.to_csv(csv_path, index=False)
            
            self.set_header("Content-Disposition", f"attachment; filename={csv_path}")
            self.set_header("Content-Type", "text/csv")
            
            with open(csv_path, "rb") as file:
                self.write(file.read())
                
        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})

class FirebaseSyncHandler(BaseHandler):
    def get(self):
        sync_to_firebase()
        self.set_header("Content-Type", "application/json")
        self.write({"message": "Firebase sync initiated."})

class AddPacketHandler(BaseHandler):
    def post(self):
        try:
            packet_data = json.loads(self.request.body)
            name = packet_data.get("name", "New Data Fire")
            pac_id = packet_data.get("pac_id", -1)
            latitude = packet_data.get("latitude", 0.0)
            longitude = packet_data.get("longitude", 0.0)
            alt = packet_data.get("alt", 0.0)
            high_temp = packet_data.get("high_temp", 0.0)
            low_temp = packet_data.get("low_temp", 0.0)
            date_received = packet_data.get("date_received", datetime.now().strftime("%Y-%m-%d"))
            time_received = packet_data.get("time_received", datetime.now().strftime("%H:%M:%S"))
            flight_id = packet_data.get("flight_id", -1)
            time_stamp = packet_data.get("time_stamp", datetime.now().timestamp())
            heading = packet_data.get("heading", 0.0)
            speed = packet_data.get("speed", 0.0)
            
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO wildfires (
                    name, pac_id, latitude, longitude, alt, 
                    high_temp, low_temp, date_received, time_received,
                    status, sync_status, time_stamp, heading, speed, flight_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, pac_id, latitude, longitude, alt,
                high_temp, low_temp, date_received, time_received,
                'active', 'pending', time_stamp, heading, speed, flight_id
            ))
            self.db.commit()
            
            # process_packet(packet, name, "pending")
            
            self.set_header("Content-Type", "application/json")
            self.write({"message": "Packet added and sync initiated."})
            
        except Exception as e:
            self.set_status(500)
            self.write({"error": f"Failed to process packet: {str(e)}"})

class FireDataHandler(BaseHandler):
    def get(self):
        """API endpoint to get fire data for map visualization"""
        try:
            cursor = self.db.cursor()
            
            date_from = self.get_argument('date_from', None)
            date_to = self.get_argument('date_to', None)
            flight_ids = self.get_arguments('flight_id')
            
            query = """
                SELECT 
                    w.id, 
                    w.name, 
                    w.latitude, 
                    w.longitude, 
                    w.date_received,
                    w.time_received,
                    w.status,
                    w.high_temp,
                    w.low_temp,
                    w.flight_id,
                    w.time_stamp
                FROM wildfires w
                WHERE 1=1
            """
            params = []
            
            if date_from:
                query += " AND w.date_received >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND w.date_received <= ?"
                params.append(date_to)
                
            if flight_ids:
                placeholders = ','.join(['?'] * len(flight_ids))
                query += f" AND w.flight_id IN ({placeholders})"
                params.extend(flight_ids)
                
            query += " GROUP BY w.id"
            
            cursor.execute(query, params)
            fires = [dict(row) for row in cursor.fetchall()]
            
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(fires))
            
        except Exception as e:
            logging.error(f"Error fetching fire data: {str(e)}")
            self.set_status(500)
            self.write({"error": "Failed to fetch fire data"})

class ThermalDataHandler(BaseHandler):
    def get(self, name):
        try:
            cursor = self.db.cursor()

            # Get optional timestamp and flight_id parameters
            time_param = self.get_argument("time_stamp", None)
            flight_id = self.get_argument("flight_id", None)

            query = """
                SELECT 
                    id,
                    name,
                    latitude,
                    longitude,
                    alt as altitude,
                    high_temp,
                    low_temp,
                    time_stamp,
                    flight_id
                FROM wildfires
                WHERE name = ?
            """
            params = [name]

            if flight_id:
                query += " AND flight_id = ?"
                params.append(int(flight_id))

            if time_param:
                dt = datetime.fromisoformat(time_param.replace("Z", "+00:00"))
                time_ns = int(dt.timestamp() * 1_000_000_000)
                query += " AND time_stamp <= ?"
                params.append(time_ns)

            query += " ORDER BY time_stamp ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            thermal_data = [dict(row) for row in rows]
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(thermal_data))

        except Exception as e:
            import traceback
            logging.error(f"ThermalDataHandler Error: {str(e)}\n{traceback.format_exc()}")
            self.set_status(500)
            self.write(json.dumps({ "error": "Failed to fetch thermal data" }))

class FlightDataHandler(BaseHandler):
    def get(self, flight_name=None):
        """API endpoint to get flight data for a specific fire and flight ID"""
        try:
            cursor = self.db.cursor()
            flight_id = self.get_argument("flight_id", None)

            if flight_id and flight_name:
                # Get one specific flight matching both fire name and ID
                query = """
                    SELECT 
                        flight_id,
                        name, 
                        ulog_filename,
                        time_started,
                        time_ended
                    FROM flights
                    WHERE name = ? AND flight_id = ?
                """
                cursor.execute(query, [flight_name, int(flight_id)])
                flight_data = cursor.fetchone()

                if flight_data:
                    flight = dict(flight_data)

                    # Get associated wildfire data
                    path_query = """
                        SELECT 
                            id,
                            name,
                            latitude,
                            longitude,
                            alt as altitude,
                            high_temp,
                            low_temp,
                            time_stamp
                        FROM wildfires
                        WHERE name = ? AND flight_id = ?
                        ORDER BY time_stamp
                    """
                    cursor.execute(path_query, [flight_name, int(flight_id)])
                    flight["wildfire_data"] = [dict(row) for row in cursor.fetchall()]

                    self.write(json.dumps(flight))
                else:
                    self.set_status(404)
                    self.write({ "error": "Flight not found" })

            else:
                # Return all flights (optional filtering with timestamps)
                query = """
                    SELECT 
                        flight_id,
                        name, 
                        ulog_filename,
                        time_started,
                        time_ended
                    FROM flights
                    WHERE 1=1
                """
                params = []

                time_from = self.get_argument('time_from', None)
                time_to = self.get_argument('time_to', None)

                if time_from:
                    query += " AND time_started >= ?"
                    params.append(float(time_from))

                if time_to:
                    query += " AND time_started <= ?"
                    params.append(float(time_to))

                cursor.execute(query, params)
                flights = [dict(row) for row in cursor.fetchall()]
                self.write(json.dumps(flights))

        except Exception as e:
            logging.error(f"Error fetching flight data: {str(e)}")
            self.set_status(500)
            self.write({ "error": "Failed to fetch flight data" })

class FlightDetailsHandler(BaseHandler):
    def get(self):
        self.render("flight_details.html")

class LiveDataWebSocketHandler(tornado.websocket.WebSocketHandler):
    """WebSocket handler for real-time data updates"""
    connections = set()
    
    def check_origin(self, origin):
        return True
    
    def open(self):
        self.connections.add(self)
        logging.info("WebSocket opened")
        
    def on_message(self, message):
        try:
            data = json.loads(message)
            command = data.get('command')
                
        except Exception as e:
            logging.error(f"WebSocket message error: {str(e)}")
            
    def on_close(self):
        self.connections.remove(self)
        logging.info("WebSocket closed")

class FireDetailsHandler(BaseHandler):
    def get(self):
        self.render("fire_details.html")

class FireComparisonHandler(BaseHandler):
    def get(self):
        fire_name = self.get_argument("name")
        cursor = self.db.cursor()

        # Get the two most recent entries
        latest_query = """
            SELECT time_stamp
            FROM wildfire_status
            WHERE name = ?
            ORDER BY time_stamp DESC
            LIMIT 2
        """
        cursor.execute(latest_query, (fire_name,))
        rows = cursor.fetchall()

        if len(rows) < 2 or rows[0]["time_stamp"] != rows[1]["time_stamp"]:
            update_fire_status(fire_name)

        current_query = """
            SELECT size, intensity, time_stamp
            FROM wildfire_status
            WHERE name = ?
            ORDER BY time_stamp DESC
            LIMIT 1
        """
        cursor.execute(current_query, (fire_name,))
        current_record = cursor.fetchone()
        if not current_record:
            self.set_status(404)
            self.write(json.dumps({"error": "Fire not found"}))
            return

        current_timestamp = current_record["time_stamp"]

        # Get the previous entry in wildfire_status
        comparison_query = """
            SELECT size, intensity, time_stamp
            FROM wildfire_status
            WHERE name = ? AND time_stamp < ?
            ORDER BY time_stamp DESC
            LIMIT 1
        """
        cursor.execute(comparison_query, (fire_name, current_timestamp))
        comparison_record = cursor.fetchone()

        if comparison_record:
            result = {
                "prev_size": comparison_record["size"],
                "prev_intensity": comparison_record["intensity"],
                "prev_timestamp": comparison_record["time_stamp"]
            }
        else:
            result = {} 

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))
        
class TestHandler(BaseHandler):
    def get(self):
        self.render("test.html")

class CurrentFlightHandler(BaseHandler):
    def get(self):
        fire_name = self.get_argument("name", "")
        flight_id = self.get_argument("flight_id", "")
        self.render(
            "current_flight.html",
            fire_name=fire_name,
            flight_id=flight_id
        )

class LiveFlightHandler(BaseHandler):
    def get(self, flight_name=None):
        """API endpoint to get flight data for a specific fire and flight ID"""
        try:
            cursor = self.db.cursor()
            flight_id = self.get_argument("flight_id", None)
            after_ns  = int(self.get_argument("after", 0))

            if flight_id and flight_name:
                # Get one specific flight matching both fire name and ID
                query = """
                    SELECT 
                        flight_id,
                        name, 
                        ulog_filename,
                        time_started,
                        time_ended
                    FROM flights
                    WHERE name = ? AND flight_id = ?
                """
                cursor.execute(query, [flight_name, int(flight_id)])
                flight_data = cursor.fetchone()

                if flight_data:
                    flight = dict(flight_data)

                    # Get associated wildfire data
                    path_query = """
                        SELECT 
                            id,
                            name,
                            latitude,
                            longitude,
                            alt as altitude,
                            high_temp,
                            low_temp,
                            time_stamp
                        FROM wildfires
                        WHERE name = ? AND flight_id = ?
                        ORDER BY time_stamp
                    """
                    cursor.execute(path_query, [flight_name, int(flight_id), after_ns])
                    flight["wildfire_data"] = [dict(row) for row in cursor.fetchall()]

                    self.write(json.dumps(flight))
                else:
                    self.set_status(404)
                    self.write({ "error": "Flight not found" })

            else:
                # Return all flights (optional filtering with timestamps)
                query = """
                    SELECT 
                        flight_id,
                        name, 
                        ulog_filename,
                        time_started,
                        time_ended
                    FROM flights
                    WHERE 1=1
                """
                params = []

                time_from = self.get_argument('time_from', None)
                time_to = self.get_argument('time_to', None)

                if time_from:
                    query += " AND time_started >= ?"
                    params.append(float(time_from))

                if time_to:
                    query += " AND time_started <= ?"
                    params.append(float(time_to))

                cursor.execute(query, params)
                flights = [dict(row) for row in cursor.fetchall()]
                self.write(json.dumps(flights))

        except Exception as e:
            logging.error(f"Error fetching flight data: {str(e)}")
            self.set_status(500)
            self.write({ "error": "Failed to fetch flight data" })

class WildfireStatusHandler(BaseHandler):
    def get(self):
        name        = self.get_argument("name", None)
        filter_type = self.get_argument("filter", "active")
        cursor      = self.db.cursor()

        if name:
            query = """
                SELECT
                    id,
                    time_stamp,
                    size,
                    flights,
                    intensity,
                    max_temp,
                    min_temp,
                    alt_avg,
                    avg_latitude,
                    avg_longitude,
                    num_data_points,
                    first_time_stamp,
                    status,
                    last_flight_id
                FROM wildfire_status
                WHERE name = ?
                ORDER BY time_stamp ASC
            """
            cursor.execute(query, (name,))
            rows = cursor.fetchall()

            data = []
            for row in rows:
                raw_ts       = row["time_stamp"]
                raw_first_ts = row["first_time_stamp"]

                ts = datetime.fromtimestamp(raw_ts / 1e9).isoformat()
                first_ts = (
                    datetime.fromtimestamp(raw_first_ts / 1e9).isoformat()
                    if raw_first_ts else None
                )

                data.append({
                    "id":               row["id"],
                    "time_stamp":       ts,
                    "first_time_stamp": first_ts,
                    "size":             row["size"],
                    "flights":          row["flights"],
                    "intensity":        row["intensity"],
                    "max_temp":         row["max_temp"],
                    "min_temp":         row["min_temp"],
                    "alt_avg":          row["alt_avg"],
                    "avg_latitude":     row["avg_latitude"],
                    "avg_longitude":    row["avg_longitude"],
                    "num_data_points":  row["num_data_points"],
                    "status":           row["status"],
                    "last_flight_id":   row["last_flight_id"]
                })

            self.set_header("Content-Type", "application/json")
            return self.write(json.dumps(data))
        
        subquery = """
            SELECT name, MAX(time_stamp) AS max_time_stamp
            FROM wildfire_status
            WHERE 1=1
        """
        params = []
        if filter_type == "active":
            subquery += " AND status = ?"
            params.append("active")
        elif filter_type == "archived":
            subquery += " AND status = ?"
            params.append("archived")

        subquery += " GROUP BY name"

        query = f"""
            SELECT 
                ws.id,
                ws.name, 
                ws.location,
                ws.size,
                ws.intensity,
                ws.alt_avg,
                ws.status,
                ws.max_temp,
                ws.min_temp,
                ws.avg_latitude,
                ws.avg_longitude,
                ws.flights,
                ws.num_data_points,
                ws.first_time_stamp, 
                ws.time_stamp,
                ws.last_flight_id
            FROM wildfire_status ws
            JOIN ({subquery}) latest 
              ON ws.name = latest.name 
             AND ws.time_stamp = latest.max_time_stamp
            ORDER BY ws.time_stamp DESC
        """

        cursor.execute(query, params)
        fires = [dict(row) for row in cursor.fetchall()]

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(fires))

def make_app():
    static_path = os.path.join(os.path.dirname(__file__), "app/static")
    template_path = os.path.join(os.path.dirname(__file__), "app/templates")
    
    return tornado.web.Application([
        # Main page routes
        (r"/", MainHandler),
        (r"/fires", FiresHandler),
        (r"/flights", FlightsHandler),
        (r"/data", DataHandler),
        (r"/about", AboutHandler),
        (r"/fire_details", FireDetailsHandler),
        (r"/flight_details", FlightDetailsHandler),
        (r"/current_flight", CurrentFlightHandler),
        
        # API routes
        (r"/heatmap_data", HeatmapDataHandler),
        (r"/wildfire_markers", WildfireMarkersHandler),
        (r"/get_database", DatabaseQueryHandler),
        (r"/download_csv", DownloadCSVHandler),
        (r"/sync_firebase", FirebaseSyncHandler),
        (r"/add_packet", AddPacketHandler),
        (r"/fire_comparison", FireComparisonHandler),
        (r"/test", TestHandler),
        (r"/api/fires", FireDataHandler),
        (r"/api/thermal/([^/]+)", ThermalDataHandler),
        (r"/api/flights", FlightDataHandler),
        (r"/api/flights/(\d+)", FlightDataHandler),
        (r"/api/flights/(.*)", FlightDataHandler),
        (r"/api/fire_status", WildfireStatusHandler),
        
        # WebSocket route for live data
        (r"/ws/live", LiveDataWebSocketHandler),
        (r"/api/live_flight/(\d+)", LiveFlightHandler),
        
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": static_path, "default_filename": "index.html"}),
    ], 
    debug=options.debug,
    template_path=template_path,
    static_path=static_path,
    )

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

def start_app():
    # Create and start the app
    app = make_app()
    app.listen(options.port)
    
    print(f"Pyro Visualization server running at http://localhost:{options.port}/")
    print(f"Debug mode: {options.debug}")

    tornado.ioloop.IOLoop.current().start()


def start_server():
    # Initialize databases
    init_db()

    # Optionally import test packets
    import_packets_from_file('all_fire_packets.txt')
    
    # Parse command line arguments
    parse_command_line()
    
    # Start the avionics integration process
    q1 = mp.Queue()
    p1 = mp.Process(target=avionics_integration, args=(q1,))
    p_server = mp.Process(target=start_app)
    p1.start()
    p_server.start()
    
    try:
        while True:
            if not q1.empty():
                data = q1.get()
                print("Received data from avionics:", data)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down backend server.")
        p1.terminate()