from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QThread
import sys
import subprocess
import time

class TornadoThread(QThread):
    def run(self):
        subprocess.call(["python", "backend_server.py"])

class WebAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wildfire Tracking Operator UI")

        self.server_thread = TornadoThread()
        self.server_thread.start()
        time.sleep(1)

        self.browser = QWebEngineView()
        self.browser.load(QUrl("http://localhost:8000/current_flight"))

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.browser)
        self.setCentralWidget(central_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebAppWindow()
    window.show()
    sys.exit(app.exec_())