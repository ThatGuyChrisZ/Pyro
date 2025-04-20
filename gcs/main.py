###########################################################################
#                                                                         #
#                      Contributed by Robb Northrup                       #
#                                                                         #
###########################################################################

import sys
import os
import subprocess
import multiprocessing as mp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                             QVBoxLayout, QWidget, QSplashScreen, QFileDialog, QLineEdit,
                             QComboBox, QMessageBox)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from serial.tools import list_ports
from radio import start_radio

class GCSMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥PYRO")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon("deskapp/assets/icons/fire.ico"))

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
        self.start_button = QPushButton("Start GCS")
        self.start_button.clicked.connect(self.start_backend_processes)
        layout.addWidget(self.start_button)

        # Stop GCS Button
        self.stop_button = QPushButton("Stop GCS")
        self.stop_button.clicked.connect(self.stop_backend_processes)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        # Container widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_backend_processes(self):
        # Run GCS main.py and backend server.py
        prog_mode = int(self.prog_mode_dropdown.currentText()[0])
        trans_port = self.transciever_port_dropdown.currentText()
        call_sign = self.callsign_input.text()
        if len(call_sign) != 6:
            QMessageBox.critical(self, "Invalid Callsign", "Callsign must be exactly 6 characters long.")
            return

        self.radio_process = mp.Process(target=start_radio, args=(prog_mode, trans_port, call_sign,))
        self.radio_process.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        print("GCS and backend started.")
        return True
    
    def stop_backend_processes(self):
        if self.radio_process and self.radio_process.is_alive():
            self.radio_process.terminate()
            self.radio_process.join()
            print("GCS and backend stopped.")

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def refresh_usb_ports(self):
        ports = list_ports.comports()
        self.transciever_port_dropdown.clear()
        for port in ports:
            self.transciever_port_dropdown.addItem(port.device)


def show_splash_screen():
    splash_pix = QPixmap('assets/splash.png')
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()
    QTimer.singleShot(3000, splash.close)
    return splash


if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = show_splash_screen()

    # Show main window after splash
    window = GCSMainWindow()
    QTimer.singleShot(3000, window.show)

    sys.exit(app.exec_())