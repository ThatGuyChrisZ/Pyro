###########################################################################
#                                                                         #
#                      Contributed by Robb Northrup                       #
#                                                                         #
###########################################################################

import sys
import os
import subprocess
import multiprocessing as mp
import signal
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import urllib.parse
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QWidget, QSplashScreen, QFileDialog, QLineEdit,
                             QComboBox, QMessageBox, QGraphicsOpacityEffect, QTabWidget,
                             QSizePolicy, QScrollArea)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt, QUrl, QProcess, QPropertyAnimation, pyqtProperty
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QPixmap
from serial.tools import list_ports
from radio import start_radio
from backend_server import start_server

radio_proc = None
server_proc = None
SPLASH_FADE_IN_TIME, SPLASH_FADE_OUT_TIME, SPLASH_HOLD_TIME = 5000, 0, 2000
icon_path = os.path.join(os.path.dirname(__file__), "deskapp", "assets", "icons", "fire.png")

def signal_handler(sig, frame):
    global radio_proc
    global server_proc
    if radio_proc is not None and radio_proc.is_alive():
        print("Terminating background processes")
        radio_proc.terminate()
        radio_proc.join()
        server_proc.terminate()
        server_proc.join()
    sys.exit(0)

# Register cleanup for Ctrl+C or parent kill
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class GCSMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥PYRO")
        self.setGeometry(100, 100, 1000, 800)
        self.prog_mode = None
        self.trans_port = None
        self.call_sign = None
        self.flight_session_name = None
        self.radio_process = None
        self.server_process = None
        self.q_transciever_functional = mp.Queue()

        # Tab Widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Add Main Tab
        self.main_tab = QWidget()
        self.tabs.addTab(self.main_tab, "Main")
        self.init_main_tab()

        # Add Map Tab
        self.map_tab = QWidget()
        self.tabs.addTab(self.map_tab, "Map")
        self.init_map_tab()

        # Add Connection Tab
        self.radio_tab = QWidget()
        self.tabs.addTab(self.radio_tab, "Connection")
        self.init_radio_tab()

        # Start Server Process!!!
        self.server_process = mp.Process(
            target=start_server,
            args=()
        )
        self.server_process.start()

        print("ICON PATH:", icon_path)
        print("Exists?", os.path.exists(icon_path))
        QTimer.singleShot(0, lambda: self.setWindowIcon(QIcon(icon_path)))

        icon = QIcon(icon_path)
        self.setWindowIcon(icon)

    def init_main_tab(self):
        # Layout
        layout = QVBoxLayout()

        # WebEngine View for Map
        # ASHTON IMPLEMENT

        # Callsign Input
        self.callsign_input = QLineEdit()
        self.callsign_input.setPlaceholderText("Enter Callsign")
        layout.addWidget(self.callsign_input)
        # INCLUDE SECTION THAT YOU NEED
        # TO BE FAA-LICENSED TO UTILIZE
        # RADIOS WITHIN A SPECIFIC FREQ
        # (HAM RADIO)

        # Flight Session Name Input
        self.flight_session_name_input = QLineEdit()
        self.flight_session_name_input.setPlaceholderText("Flight Session Name")
        layout.addWidget(self.flight_session_name_input)

        # Program Mode Dropdown
        self.prog_mode_dropdown = QComboBox()
        self.prog_mode_dropdown.addItems(["0 - NORMAL OPERATION", "1 - DEBUG MODE", "2 - LOCAL DEBUG MODE"])
        layout.addWidget(QLabel("Select Program Mode:"))
        layout.addWidget(self.prog_mode_dropdown)

        # Transceiver Port Dropdown
        self.transciever_port_dropdown = QComboBox()
        self.refresh_usb_ports()
        layout.addWidget(QLabel("Select Transceiver Port:"))
        layout.addWidget(self.transciever_port_dropdown)

        #prog_mode + transciever port input
        # self.prog_mode_input = QLineEdit()
        # self.prog_mode_input.setPlaceholderText("Enter Program Mode")
        # layout.addWidget(self.prog_mode_input)
        # self.transciever_port_input = QLineEdit()
        # self.transciever_port_input.setPlaceholderText("Enter transciever Input")
        # layout.addWidget(self.transciever_port_input)

        # Start GCS + Backend
        self.start_button = QPushButton("Start Thermal Imaging Retrieval")
        self.start_button.clicked.connect(self.start_backend_processes)
        layout.addWidget(self.start_button)

        # Stop GCS Button
        self.stop_button = QPushButton("Stop Thermal Imaging Retrieval")
        self.stop_button.clicked.connect(self.stop_backend_processes)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.main_tab.setLayout(layout)

    def init_map_tab(self):
        layout = QVBoxLayout()

        # Create the QWebEngineView widget to display the webpage
        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        # Initially set the layout for the map tab
        self.map_tab.setLayout(layout)

        # Try to load the map immediately
        self.try_load_map()

    def populate_session_dropdown(self):
        log_dir = "trans_logs"
        sessions = set()

        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                if filename.endswith(".csv"):
                    session_name = filename.replace(".csv", "")
                    sessions.add(session_name)

        self.session_dropdown.addItems(sorted(sessions))

    def load_selected_map(self, session_name):
        if session_name:
            encoded = urllib.parse.quote(session_name)
            url = f"http://localhost:8000/current_flight?name={encoded}"
        else:
            url = "http://localhost:8000/"
        self.webview.setUrl(QUrl(url))


    def try_load_map(self):
        name = self.flight_session_name or self.flight_session_name_input.text()
        if name:
            encoded = urllib.parse.quote(name)
            url = f"http://localhost:8000/current_flight?name={encoded}"
        else:
            url = "http://localhost:8000/"
        qurl = QUrl(url)

        try:
            self.webview.loadFinished.disconnect()
        except TypeError:
            pass

        def on_load_finished(success):
            if not success and self.prog_mode != 0:
                print(f"[Map] Failed to load {url}")
        self.webview.loadFinished.connect(on_load_finished)
        self.webview.setUrl(qurl)

    def show_map_tab(self):
        name = self.flight_session_name or self.flight_session_name_input.text()
        encoded = urllib.parse.quote(name) if name else ""
        url = f"http://localhost:8000/current_flight?name={encoded}" if name else "http://localhost:8000/"
        self.webview.setUrl(QUrl(url))


    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Map":
            self.show_map_tab()

    def init_radio_tab(self):
        layout = QVBoxLayout()

        self.radio_status_label = QLabel()
        layout.addWidget(self.radio_status_label)

        self.generate_graph_button = QPushButton("Generate Radio Graphs")
        self.generate_graph_button.clicked.connect(self.display_radio_graphs)
        layout.addWidget(self.generate_graph_button)

        # Stats area (key metrics as labels)
        self.radio_stats_label = QLabel()
        self.radio_stats_label.setAlignment(Qt.AlignLeft)
        self.radio_stats_label.setWordWrap(True)
        layout.addWidget(self.radio_stats_label)

        # Scrollable area for graph
        scroll_area = QScrollArea()
        self.radio_graph_label = QLabel()
        self.radio_graph_label.setAlignment(Qt.AlignCenter)
        self.radio_graph_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.radio_graph_label)
        layout.addWidget(scroll_area)

        self.radio_tab.setLayout(layout)



    def display_radio_graphs(self):
        try:
            sns.set_theme(style="whitegrid")
            log_dir = "trans_logs"
            csv_files = [f for f in os.listdir(log_dir) if f.endswith(".csv")]
            if not csv_files:
                self.radio_status_label.setText("No logs found.")
                return

            latest_file = max(csv_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
            df = pd.read_csv(os.path.join(log_dir, latest_file))

            df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
            df["packet_id"] = pd.to_numeric(df["packet_id"], errors='coerce')
            df.dropna(subset=["timestamp", "packet_id"], inplace=True)

            recv_df = df[df["send(s)/receive(r)"] == "r"]

            # ==== KEY METRICS ====
            total_packets = len(df)
            total_received = len(recv_df)
            corruption_rate = df["corrupted"].mean() * 100
            avg_transmissions = df["num_transmissions"].mean()

            metrics_text = f"""
            <b>Latest Session Metrics:</b><br>
            Total Packets Logged: {total_packets}<br>
            Total Received: {total_received}<br>
            Avg. Transmissions per Packet: {avg_transmissions:.2f}<br>
            Overall Corruption Rate: <span style='color:red'>{corruption_rate:.2f}%</span><br>
            """
            self.radio_stats_label.setText(metrics_text)

            # ==== MISSING PACKET CALC ====
            missing_summary = []
            for session_id in df["session_id"].unique():
                sent_ids = set(df[(df["session_id"] == session_id) & (df["send(s)/receive(r)"] == "s")]["packet_id"])
                recv_ids = set(df[(df["session_id"] == session_id) & (df["send(s)/receive(r)"] == "r")]["packet_id"])
                missing = sent_ids - recv_ids
                if missing:
                    missing_summary.append((session_id, len(missing)))

            total_missing = sum(m[1] for m in missing_summary)
            missing_lines = "".join(
                f"Session {sid}: {count} missing<br>" for sid, count in missing_summary
            )

            metrics_text = f"""
            <b>Latest Session Metrics:</b><br>
            Total Packets Logged: {total_packets}<br>
            Total Received: {total_received}<br>
            Avg. Transmissions per Packet: {avg_transmissions:.2f}<br>
            Overall Corruption Rate: <span style='color:red'>{corruption_rate:.2f}%</span><br>
            Dropped Packets Not Received: <span style='color:orange'>{total_missing}</span><br>
            {missing_lines}
            """
            self.radio_stats_label.setText(metrics_text)

            # ==== GRAPH PLOTTING ====
            fig, axs = plt.subplots(2, 2, figsize=(16, 10))
            axs = axs.flatten()

            # 1. Retransmissions by Packet Type
            retrans_avg = df.groupby("pac_type")["num_transmissions"].mean().reset_index()
            sns.barplot(data=retrans_avg, x="pac_type", y="num_transmissions", ax=axs[0], palette="rocket")
            axs[0].set_title("Avg. Transmissions per Packet Type")

            # 2. Missing Packets per Session
            for session_id in recv_df["session_id"].unique():
                s_df = recv_df[recv_df["session_id"] == session_id]
                expected_ids = range(int(s_df["packet_id"].min()), int(s_df["packet_id"].max()) + 1)
                received_ids = s_df["packet_id"].unique()
                missing = sorted(set(expected_ids) - set(received_ids))
                axs[1].plot(received_ids, [session_id] * len(received_ids), label=f"Session {session_id}")
                axs[1].scatter(missing, [session_id] * len(missing), c="red", marker="x", s=50, label=f"Missing {session_id}")
            axs[1].set_title("Missing Packet IDs by Session")
            axs[1].legend()

            # 3. Out-of-Order Detection
            recv_sorted = recv_df.sort_values("timestamp")
            recv_sorted["expected"] = recv_sorted["packet_id"].cummin()
            recv_sorted["out_of_order"] = recv_sorted["packet_id"] < recv_sorted["expected"]
            sns.scatterplot(data=recv_sorted, x="timestamp", y="packet_id", hue="out_of_order", ax=axs[2], palette="dark")
            axs[2].set_title("Out-of-Order Packets")

            # 4. Packet Arrival Trend
            recv_df["minute"] = recv_df["timestamp"].dt.floor("min")
            trend = recv_df.groupby("minute")["packet_id"].count().reset_index()
            sns.lineplot(data=trend, x="minute", y="packet_id", ax=axs[3], color="green")
            axs[3].set_title("Packet Arrival Over Time")
            axs[3].set_ylabel("# Packets")

            for ax in axs:
                ax.tick_params(axis='x', rotation=15)
                ax.grid(True, linestyle='--', alpha=0.6)

            plt.tight_layout()
            graph_path = os.path.join(log_dir, "radio_graph.png")
            plt.savefig(graph_path, dpi=200)
            plt.close()

            pixmap = QPixmap(graph_path)
            scaled_pixmap = pixmap.scaled(self.radio_graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.radio_graph_label.setPixmap(scaled_pixmap)

        except Exception as e:
            self.radio_status_label.setText(f"Error generating graph: {e}")



    def start_backend_processes(self):
        self.prog_mode = int(self.prog_mode_dropdown.currentText()[0])
        self.trans_port = self.transciever_port_dropdown.currentText()
        self.call_sign = self.callsign_input.text()
        self.flight_session_name = self.flight_session_name_input.text()

        self.try_load_map()

        if len(self.call_sign) != 6:
            QMessageBox.critical(self, "Invalid Callsign", "Callsign must be exactly 6 characters long.")
            return

        # Clear the queue
        while not self.q_transciever_functional.empty():
            try:
                self.q_transciever_functional.get_nowait()
            except:
                break

        # Start fresh process
        self.radio_process = mp.Process(
            target=start_radio,
            args=(self.prog_mode, self.trans_port, self.call_sign, self.flight_session_name, self.q_transciever_functional)
        )
        self.radio_process.start()

        # Wait for radio confirmation
        try:
            transceiver_ok = self.q_transciever_functional.get(timeout=50)
            if self.prog_mode != 0:
                print(f"[start_backend_processes] Transceiver OK? {transceiver_ok}")
        except:
            transceiver_ok = False
            if self.prog_mode != 0:
                print("[start_backend_processes] No response from radio process in time.")

        if not transceiver_ok:
            self.radio_process.terminate()
            self.radio_process.join()
            QMessageBox.critical(self, "Transceiver Error", f"Could not connect to transceiver at {self.trans_port}.")
            if self.prog_mode != 0:
                print("[start_radio] Backend terminated due to transceiver error.")
            return

        # Success
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        if self.prog_mode != 0:
            print("[start_radio] Backend started successfully.")

    
    def stop_backend_processes(self):
        if self.radio_process and self.radio_process.is_alive():
            self.close_radio_child_processes()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def refresh_usb_ports(self):
        ports = list_ports.comports()
        self.transciever_port_dropdown.clear()
        
        # Filter to include only devices with 'tty' in the name (e.g., ttyUSB0, ttyACM0)
        for port in ports:
            if 'ttyUSB' in port.device or 'COM' in port.device:
                self.transciever_port_dropdown.addItem(port.device)

    def closeEvent(self, event):
        if self.radio_process != None and self.radio_process.is_alive():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Closing PYRO will terminate data retrieval from the drone. Are you sure you wish to proceed?")
            msg.setWindowTitle("WARNING")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            reply = msg.exec_()
            if reply == QMessageBox.Yes:
                self.close_child_processes()
                event.accept()
                # print("before kill 1")
                # os.kill(os.getpid(), signal.SIGINT)  # Triggers signal handler
                # print("after kill 1")
            else:
                event.ignore()
        else:
            self.close_child_processes() #should ignore radio process, since it isn't live
            event.accept()
            sys.exit(0)
            # print("before kill 2")
            # os.kill(os.getpid(), signal.SIGINT)  # Triggers signal handler
            # print("after kill 2")

    def close_radio_child_processes(self):
        self.radio_process.terminate()
        self.radio_process.join(timeout=5)
        if self.radio_process.is_alive():
            if self.prog_mode != 0:
                print("FORCE KILLING [start_radio]")
                print("GCS and backend stopped.")

    def close_child_processes(self):
        if self.radio_process != None and self.radio_process.is_alive():
            self.radio_process.terminate()
            self.radio_process.join(timeout=5)
        self.server_process.terminate()
        self.server_process.join(timeout=5)
        if self.prog_mode != 0:
            print("FORCE KILLING [start_radio] and [start_server]")
            print("GCS and backend stopped.")

#
#   THIS CLASS (FadingSplashScreen) WAS CREATED USING AN LLM (why would I program this myself??)
#
class FadingSplashScreen(QSplashScreen):
    def __init__(self, pixmap):
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setMask(pixmap.mask())

        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self._opacity = 0.0
        self.opacity_effect.setOpacity(self._opacity)

        self.fade_in_anim = QPropertyAnimation(self, b"opacity")
        self.fade_in_anim.setDuration(SPLASH_FADE_IN_TIME)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(1.0)

        self.fade_out_anim = QPropertyAnimation(self, b"opacity")
        self.fade_out_anim.setDuration(SPLASH_FADE_OUT_TIME)
        self.fade_out_anim.setStartValue(1.0)
        self.fade_out_anim.setEndValue(0.0)
        self.fade_out_anim.finished.connect(self.close)

    def fade_in(self):
        self.fade_in_anim.start()

    def fade_out(self):
        self.fade_out_anim.start()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.opacity_effect.setOpacity(value)

    opacity = pyqtProperty(float, get_opacity, set_opacity)

def show_splash_screen(app):
    splash_pix = QPixmap("deskapp/assets/logos/basic.png")
    splash = FadingSplashScreen(splash_pix)
    splash.show()
    splash.raise_()
    splash.activateWindow()
    app.processEvents()
    splash.fade_in()

    # Wait 
    QTimer.singleShot(SPLASH_HOLD_TIME, splash.fade_out)
    return splash


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Show splash screen with fade
    splash = show_splash_screen(app)
    total_splash_time = SPLASH_FADE_IN_TIME + SPLASH_FADE_OUT_TIME


    # Show main window slightly after splash fade-out
    window = GCSMainWindow()

    QTimer.singleShot(SPLASH_HOLD_TIME, window.show)  # total splash time = fade in + delay + fade out

    sys.exit(app.exec_())