from pymavlink import mavutil


import time
import math

def recursive_listen(QGroundControl):
    QGroundControl.wait_heartbeat()
    Attitude = QGroundControl.recv_match(type='ATTITUDE', blocking=True)
    Altitude = QGroundControl.recv_match(type='ALTITUDE', blocking=True)
    Heading = QGroundControl.recv_match(type='VFR_HUD', blocking=True)
    mailbox = QGroundControl.messages.keys()
    enable = 1
    if enable == 2:
        for mail in mailbox:
            print("____________________________________")
            print(mail)
    
    if enable == 1:
        print("_______________________________")
        print("Pitch: ", Attitude.pitch)
        print("Roll:", Attitude.roll)
        print("Yaw:", Attitude.yaw)
        print("Altitudee",Altitude.altitude_amsl)
        print("Heading: ",Heading.heading)
        print("Ground Speed: ",Heading.groundspeed)
        new_time = time.time()
        local_time = time.localtime(new_time)
        rounded_time = round(float(new_time),1)
        print("Time_Stamp", rounded_time)
        
        
    recursive_listen(QGroundControl)

def main():
    print("Program Started")
    QGroundControl = mavutil.mavlink_connection('udpin:localhost:14445')
    recursive_listen(QGroundControl)
    
if __name__=="__main__":
    main()