import serial

try:
    s = serial.Serial("COM4", 57600)
    print("Connected successfully.")
    s.close()
except Exception as e:
    print("Failed to connect:", e)
