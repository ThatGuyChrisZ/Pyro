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
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QWidget, QSplashScreen, QFileDialog, QLineEdit,
                             QComboBox, QMessageBox, QGraphicsOpacityEffect, QTabWidget)
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

def signal_handler(sig, frame):
    global radio_proc
    global server_proc
    if radio_proc is not None and radio_proc.is_alive():
        print("Terminating radio_proc")
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
        self.setGeometry(100, 100, 1920, 1500)
        self.setWindowIcon(QIcon("deskapp/assets/icons/fire.ico"))
        self.prog_mode = None
        self.trans_port = None
        self.call_sign = None
        self.flight_session_name = None
        self.q_transciever_functional = mp.Queue()

        # Tab Widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

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

    def try_load_map(self):
        # Attempt to load the page
        url = "http://localhost:8000/"
        
        # Convert the string URL to a QUrl object
        qurl = QUrl(url)

        # Check if the page is loaded successfully
        def on_load_finished(success):
            if success:
                pass
            else:
                if self.prog_mode != 0:
                    print("Failed to load map. Retrying...")
                self.map_label.setText("Retrying to load map...")

        # Set the callback for when the page has finished loading
        self.webview.loadFinished.connect(on_load_finished)

        # Load the map page
        self.webview.setUrl(qurl)


    def init_radio_tab(self):
        layout = QVBoxLayout()

        # Add a button to trigger graph generation
        self.generate_graph_button = QPushButton("Generate Radio Graphs")
        self.generate_graph_button.clicked.connect(self.display_radio_graphs)
        layout.addWidget(self.generate_graph_button)

        # Label to show the graph image
        self.radio_graph_label = QLabel()
        self.radio_graph_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.radio_graph_label)

        self.radio_tab.setLayout(layout)


    def start_backend_processes(self):
        self.prog_mode = int(self.prog_mode_dropdown.currentText()[0])
        self.trans_port = self.transciever_port_dropdown.currentText()
        self.call_sign = self.callsign_input.text()
        self.flight_session_name = self.flight_session_name_input.text()

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

        # ✅ Success
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
        for port in ports:
            self.transciever_port_dropdown.addItem(port.device)

    def closeEvent(self, event):
        if self.radio_process.is_alive():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Closing PYRO will terminate data retrieval from the drone. Are you sure you wish to proceed?")
            msg.setWindowTitle("WARNING")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            reply = msg.exec_()
            if reply == QMessageBox.Yes:
                self.close_child_processes()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def close_radio_child_processes(self):
        self.radio_process.terminate()
        self.radio_process.join(timeout=5)
        if self.radio_process.is_alive():
            if self.prog_mode != 0:
                print("FORCE KILLING [start_radio]")
                print("GCS and backend stopped.")

    def close_child_processes(self):
        self.radio_process.terminate()
        self.radio_process.join(timeout=5)
        self.server_process.terminate()
        self.server_process.join(timeout=5)
        if self.radio_process.is_alive():
            if self.prog_mode != 0:
                print("FORCE KILLING [start_radio] and [start_server]")
                print("GCS and backend stopped.")

    def display_radio_graphs(self):
        try:
            log_dir = "trans_logs"
            all_data = []
            for file in os.listdir(log_dir):
                if file.endswith(".csv"):
                    df = pd.read_csv(os.path.join(log_dir, file))
                    all_data.append(df)

            if not all_data:
                self.radio_status_label.setText("No logs found.")
                return

            df = pd.concat(all_data, ignore_index=True)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
            df["packet_id"] = pd.to_numeric(df["packet_id"], errors='coerce')
            df.dropna(subset=["timestamp", "packet_id"], inplace=True)

            fig, axs = plt.subplots(3, 2, figsize=(30, 24))
            axs = axs.flatten()

            # 1. % Corrupted Packets
            corruption_rate = df.groupby("pac_type")["corrupted"].mean().reset_index()
            sns.barplot(data=corruption_rate, x="pac_type", y="corrupted", ax=axs[0])
            axs[0].set_title("Percentage of Corrupted Packets")
            axs[0].set_ylabel("Corruption Rate")

            # 2. Retransmissions per pac_type
            retrans_avg = df.groupby("pac_type")["num_transmissions"].mean().reset_index()
            sns.barplot(data=retrans_avg, x="pac_type", y="num_transmissions", ax=axs[1])
            axs[1].set_title("Average Retransmissions by Packet Type")
            axs[1].set_ylabel("Avg. Transmissions")

            # 3. Missing Packets
            recv_df = df[df["send(s)/receive(r)"] == "r"]
            for session_id in recv_df["session_id"].unique():
                s_df = recv_df[recv_df["session_id"] == session_id]
                expected_ids = range(int(s_df["packet_id"].min()), int(s_df["packet_id"].max()) + 1)
                received_ids = s_df["packet_id"].unique()
                missing = sorted(set(expected_ids) - set(received_ids))
                axs[2].plot(received_ids, label=f"Session {session_id}")
                axs[2].scatter(missing, [-1]*len(missing), c="red", marker="x", label=f"Missing {session_id}")
            axs[2].set_title("Received vs Missing Packet IDs")
            axs[2].set_xlabel("Packet ID")
            axs[2].legend(loc='upper right')

            # 4. Out-of-order Packets
            recv_sorted = recv_df.sort_values("timestamp")
            recv_sorted["expected"] = recv_sorted["packet_id"].cummin()
            recv_sorted["out_of_order"] = recv_sorted["packet_id"] < recv_sorted["expected"]
            sns.scatterplot(data=recv_sorted, x="timestamp", y="packet_id", hue="out_of_order", ax=axs[3])
            axs[3].set_title("Out-of-Order Packet Detection")
            axs[3].legend(title="Out of Order")

            # 5. Retransmission Histogram
            sns.histplot(data=recv_df, x="num_transmissions", bins=range(1, recv_df["num_transmissions"].max()+2), ax=axs[4])
            axs[4].set_title("Histogram of Retransmissions")
            axs[4].set_xlabel("# Transmissions")

            # Hide unused subplot (bottom-right)
            axs[5].axis("off")

            # Save plot
            graph_path = os.path.join(log_dir, "radio_graph.png")
            plt.tight_layout()
            plt.savefig(graph_path)
            plt.close()

            # Display in QLabel
            pixmap = QPixmap(graph_path)
            self.radio_graph_label.setPixmap(pixmap.scaledToWidth(800, Qt.SmoothTransformation))

        except Exception as e:
            self.radio_status_label.setText(f"Error generating graph: {e}")




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