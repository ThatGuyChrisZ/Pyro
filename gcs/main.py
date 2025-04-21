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
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QWidget, QSplashScreen, QFileDialog, QLineEdit,
                             QComboBox, QMessageBox, QGraphicsOpacityEffect)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt, QUrl, QProcess, QPropertyAnimation, pyqtProperty
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QPixmap
from serial.tools import list_ports
from radio import start_radio

radio_proc = None
SPLASH_FADE_IN_TIME, SPLASH_FADE_OUT_TIME, SPLASH_HOLD_TIME = 5000, 0, 2000

def signal_handler(sig, frame):
    global radio_proc
    if radio_proc is not None and radio_proc.is_alive():
        print("Terminating radio_proc")
        radio_proc.terminate()
        radio_proc.join()
    sys.exit(0)

# Register cleanup for Ctrl+C or parent kill
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class GCSMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥PYRO")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon("deskapp/assets/icons/fire.ico"))
        self.prog_mode = None
        self.trans_port = None
        self.call_sign = None
        self.q_transciever_functional = mp.Queue()

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

        # Container widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_backend_processes(self):
        self.prog_mode = int(self.prog_mode_dropdown.currentText()[0])
        self.trans_port = self.transciever_port_dropdown.currentText()
        self.call_sign = self.callsign_input.text()

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
            args=(self.prog_mode, self.trans_port, self.call_sign, self.q_transciever_functional)
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
            self.close_child_processes()

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

    def close_child_processes(self):
        self.radio_process.terminate()
        self.radio_process.join(timeout=5)
        if self.radio_process.is_alive():
            if self.prog_mode != 0:
                print("FORCE KILLING [start_radio]")
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

# if __name__ == "__main__":
#     app = QApplication(sys.argv)

#     # Show splash first
#     splash = show_splash_screen()

#     # Load main window after splash
#     window = GCSMainWindow()
#     QTimer.singleShot(3000, window.show)

#     sys.exit(app.exec_())