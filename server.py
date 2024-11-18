from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json
import sqlite3
import pandas as pd
from database import init_db, import_csv_to_db, fetch_wildfire_data, fetch_fire_list, fetch_heatmap_data, fetch_all_heatmap_data

init_db()
import_csv_to_db('testdata.csv')

class NavigationHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        if parsed_path.path == "/wildfire_list":
            filter_type = query_params.get("filter", ["active"])[0]
            fire_data = fetch_fire_list(filter_type)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(fire_data).encode())

        elif parsed_path.path == "/heatmap_data":
            fire_name = query_params.get("name", [None])[0]
            if fire_name:
                heatmap_data = fetch_heatmap_data(fire_name) 
            else:
                heatmap_data = fetch_all_heatmap_data()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(heatmap_data).encode())

        elif parsed_path.path == "/wildfire_markers":
            filter_type = query_params.get("filter", ["active"])[0]
            wildfire_data = fetch_fire_list(filter_type)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(wildfire_data).encode())

        elif parsed_path.path == "/get_database":
            try:
                conn = sqlite3.connect("wildfire_data.db")
                df = pd.read_sql_query("SELECT * FROM wildfires", conn)
                conn.close()
                data = df.to_dict(orient="records")

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

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
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            super().do_GET()

# Run the server
if __name__ == "__main__":
    host_name = "localhost"
    port_number = 8000
    server = HTTPServer((host_name, port_number), NavigationHandler)
    print(f"Server running at http://{host_name}:{port_number}/")
    server.serve_forever()