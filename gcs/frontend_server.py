import os
import json
import sqlite3
import logging
import pandas as pd
from datetime import datetime
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.options import define, options, parse_command_line
from urllib.parse import parse_qs
from database import init_db, process_packet, fetch_fire_list, fetch_heatmap_data, fetch_all_heatmap_data, sync_to_firebase

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
                name,
                AVG(latitude) AS avg_latitude,
                AVG(longitude) AS avg_longitude,
                MAX(high_temp) AS high_temp,
                MIN(low_temp) AS low_temp,
                MAX(date_received) AS last_date_received,
                MAX(time_received) AS last_time_received,
                MAX(status) AS status,
                MAX(alt) AS alt,
                MAX(heading) AS heading,
                MAX(speed) AS speed,
                MAX(flight_id) AS flight_id,
                MAX(time_stamp) AS last_updated,
                COUNT(*) AS point_count
            FROM wildfires
            WHERE 1=1
        """

        if filter_type == "active":
            query += " AND status = 'active'"
        elif filter_type == "archived":
            query += " AND status = 'archived'"

        query += " GROUP BY name ORDER BY last_updated DESC"

        cursor.execute(query)
        fires = [dict(row) for row in cursor.fetchall()]

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(fires))

class DatabaseQueryHandler(BaseHandler):
    def get(self):
        try:
            fire_name = self.get_argument("fire_name", None)
            table = self.get_argument("table", "wildfire_status")  # default to status view
            conn = sqlite3.connect(options.db_path)

            if fire_name and table == "wildfires":
                query = "SELECT * FROM wildfires WHERE name = ?"
                df = pd.read_sql_query(query, conn, params=(fire_name,))
            else:
                if table not in ["wildfire_status", "wildfires"]:
                    raise ValueError("Invalid table name")
                query = f"SELECT * FROM {table}"
                df = pd.read_sql_query(query, conn)

            conn.close()
            data = df.to_dict(orient="records")

            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(data))

        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})

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
        # Manually trigger Firebase sync for any pending data
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

from datetime import datetime

class ThermalDataHandler(BaseHandler):
    def get(self, name):
        try:
            cursor = self.db.cursor()

            # Get optional timestamp parameter
            time_param = self.get_argument("time_stamp", None)

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
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({ "error": "Failed to fetch thermal data" }))


class FlightDataHandler(BaseHandler):
    def get(self, flight_id=None):
        """API endpoint to get flight data"""
        try:
            cursor = self.db.cursor()
            
            if flight_id:
                query = """
                    SELECT 
                        flight_id,
                        name, 
                        ulog_filename,
                        time_started,
                        time_ended
                    FROM flights
                    WHERE flight_id = ?
                """
                cursor.execute(query, [flight_id])
                flight_data = cursor.fetchone()
                
                if flight_data:
                    flight = dict(flight_data)
                    
                    # Get associated wildfire data for this flight
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
                        WHERE flight_id = ?
                        ORDER BY time_stamp
                    """
                    cursor.execute(path_query, [flight_id])
                    path_data = [dict(row) for row in cursor.fetchall()]
                    flight['wildfire_data'] = path_data
                    
                    self.write(json.dumps(flight))
                else:
                    self.set_status(404)
                    self.write({"error": "Flight not found"})
            else:
                # Get list of all flights, possibly filtered
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
            self.write({"error": "Failed to fetch flight data"})

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
        
class TestHandler(BaseHandler):
    def get(self):
        self.render("test.html")

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
        
        # API routes
        (r"/heatmap_data", HeatmapDataHandler),
        (r"/wildfire_markers", WildfireMarkersHandler),
        (r"/get_database", DatabaseQueryHandler),
        (r"/download_csv", DownloadCSVHandler),
        (r"/sync_firebase", FirebaseSyncHandler),
        (r"/add_packet", AddPacketHandler),
        (r"/test", TestHandler),
        (r"/api/fires", FireDataHandler),
        (r"/api/thermal/([^/]+)", ThermalDataHandler),
        (r"/api/flights", FlightDataHandler),
        (r"/api/flights/(\d+)", FlightDataHandler),
        
        # WebSocket route for live data
        (r"/ws/live", LiveDataWebSocketHandler),
        
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
                    process_packet(packet_data, name, 2, "active")
                except json.JSONDecodeError as e:
                    print(f"Error decoding packet: {e}")
                except Exception as e:
                    print(f"Error processing packet: {e}")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error reading file: {e}")

def main():
    # Initialize database
    init_db()

    # Optionally import test packets
    import_packets_from_file('test_packets.txt')
    
    # Parse command line arguments
    parse_command_line()
    
    # Create and start the app
    app = make_app()
    app.listen(options.port)
    
    print(f"Pyro Visualization server running at http://localhost:{options.port}/")
    print(f"Debug mode: {options.debug}")
    
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()