import sys
import subprocess
import sqlite3
import os
import firebase_admin
import time
import requests
from firebase_admin import credentials, db
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel
from database import init_db

# Initialize database before accessing it
init_db()

# Firebase Config
FIREBASE_CONFIG_PATH = "firebase_credentials.json"
DATABASE_PATH = "wildfire_data.db"
FIREBASE_DB_URL = "https://pyro-fire-tracking-default-rtdb.firebaseio.com/"

# Check if Firebase is already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CONFIG_PATH)
    firebase_admin.initialize_app(cred)

class GroundControlUI(QWidget):
    def __init__(self):
        super().__init__()

        self.server_process = None
        self.main_process = None 

        self.setWindowTitle("Ground Control UI")
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        self.start_button = QPushButton("Start Receiving Data")
        self.start_button.clicked.connect(self.start_server)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Receiving Data")
        self.stop_button.clicked.connect(self.stop_server)
        layout.addWidget(self.stop_button)

        # Logs Display
        self.logs_label = QLabel("Received Data Logs:")
        layout.addWidget(self.logs_label)

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        layout.addWidget(self.logs_text)

        # Sync Button
        self.sync_button = QPushButton("Sync Data to Firebase")
        self.sync_button.clicked.connect(self.sync_to_firebase)
        layout.addWidget(self.sync_button)

        self.setLayout(layout)
        self.load_logs()

    def start_server(self):
        """Start main_for_testing.py and server.py for receiving data"""
        self.logs_text.clear()
        self.logs_text.append("🛠 Starting main_for_testing.py and server.py...")

        if self.server_process is None and self.main_process is None:
            try:
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))

                self.main_process = subprocess.Popen(
                    ["python", os.path.join(BASE_DIR, "main_for_testing.py")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
                )

                self.server_process = subprocess.Popen(
                    ["python", os.path.join(BASE_DIR, "server.py")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
                )

                timeout = 5
                start_time = time.time()

                while time.time() - start_time < timeout:
                    try:
                        response = requests.get("http://localhost:8000/wildfire_list", timeout=2)
                        if response.status_code == 200:
                            self.logs_text.append("✅ Server started successfully!")
                            return
                    except requests.exceptions.RequestException:
                        time.sleep(1)

                self.logs_text.append("⚠ Server took too long to start.")

            except Exception as e:
                self.logs_text.append(f"❌ Failed to start processes: {e}")


    def stop_server(self):
        if self.server_process or self.main_process:
            if self.main_process:
                self.main_process.terminate()
                self.main_process = None
            if self.server_process:
                self.server_process.terminate()
                self.server_process = None
            self.logs_text.append("❌ Data reception stopped")


    def load_logs(self):
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name, latitude, longitude, high_temp, low_temp, status , sync_status FROM wildfires ORDER BY id DESC LIMIT 10")
            data = cursor.fetchall()
            conn.close()

            if not data:
                self.logs_text.append("No data received yet.")
            else:
                for row in data:
                    log_entry = f"🔥 {row[0]} | 📍({row[1]}, {row[2]}) | 🌡 {row[3]}°F - {row[4]}°F | Status: {row[5]}"
                    self.logs_text.append(log_entry)
        except sqlite3.OperationalError as e:
            self.logs_text.append(f"❌ Database error: {e}\nMake sure the server is started first.")

    def sync_to_firebase(self):
        try:
            if not os.path.exists(FIREBASE_CONFIG_PATH):
                self.logs_text.append("⚠ Firebase credentials missing.")
                return

            # Initialize Firebase
            if not firebase_admin._apps:
                cred = credentials.Certificate(FIREBASE_CONFIG_PATH)
                firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wildfires WHERE sync_status = 'pending'")
            unsynced_data = cursor.fetchall()

            if not unsynced_data:
                self.logs_text.append("✅ No new data to sync.")
            else:
                ref = db.reference("wildfires")

                for row in unsynced_data:
                    fire_data = {
                        "name": row[1],
                        "latitude": row[3],
                        "longitude": row[4],
                        "high_temp": row[6],
                        "low_temp": row[7],
                        "status": "active",
                        "sync_status": "pending"
                    }
                    ref.push(fire_data)
                    cursor.execute("UPDATE wildfires SET sync_status = 'synced' WHERE id = ?", (row[0],))

                conn.commit()
                self.logs_text.append("✅ Data synced successfully!")

        except Exception as e:
            self.logs_text.append(f"❌ Sync failed: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GroundControlUI()
    window.show()
    sys.exit(app.exec())