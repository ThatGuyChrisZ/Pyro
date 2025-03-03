from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json
import sqlite3
import pandas as pd
from database import (
    init_db,
    process_packet,
    fetch_fire_list,
    fetch_heatmap_data,
    fetch_all_heatmap_data
)

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

init_db()
import_packets_from_file('test_packets.txt')


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
                pac_id = packet_data.get("pac_id")
                gps_data = packet_data.get("gps_data", [0.0, 0.0])
                alt = packet_data.get("alt", 0.0)
                high_temp = packet_data.get("high_temp", 0.0)
                low_temp = packet_data.get("low_temp", 0.0)

                packet = {
                    "pac_id": pac_id,
                    "gps_data": gps_data,
                    "alt": alt,
                    "high_temp": high_temp,
                    "low_temp": low_temp,
                }

                process_packet(packet, name, "active")
                self._send_json_response({"message": "Packet added successfully"})
            except Exception as e:
                self._send_error_response(f"Failed to process packet: {str(e)}")

        else:
            self.send_error(404, "Endpoint not found")

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


# Run the server
if __name__ == "__main__":
    host_name = "localhost"
    port_number = 8000
    server = HTTPServer((host_name, port_number), NavigationHandler)
    print(f"Server running at http://{host_name}:{port_number}/scorch")
    server.serve_forever()
