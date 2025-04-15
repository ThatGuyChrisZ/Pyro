import subprocess
import time
from pyulog import ULog
file = "log_22_2025-3-21-17-08-16.ulg"
log_path = "C:/Users/warbr/Documents/GitHub/Pyro/Flight Logs/" + file

subprocess.call(['ulog2csv','-o','.\output', log_path])

log_file = ULog(log_path)
flight_data = []
for data in log_file.data_list:
#        print(f"Message Name: {data.name}")
#        #print(f"Number of data points: {len(data.data['timestamp'])}")
#        #print(f"Timestamps: {data.data['timestamp'][:10]}")
#        print(data.data)
        if  data.name == 'vehicle_gps_position':
            #print(data.data)
            print("timestamp")
            print(data.data['timestamp'])
            print("latitude")
            print(data.data['lat'])
            print("longitude")
            print(data.data['lon'])
            print("altitude")
            print(data.data['alt'])
            count = 0
            for entry in data.data:
                  timestamp = data.data['timestamp'][count]
                  lat = data.data['lat'][count]
                  lon = data.data['lon'][count]
                  alt = data.data['alt'][count]
                  flight_data.append((timestamp,lat,lon,alt))
                  count+=1

                  
#            #print(f"vehicle_gps_position values: {data.data['vehicle_gps_position'][:10]}")
print("Flight Data:")
#print(flight_data)


print("beginning Sim: ")

for entry in flight_data:
    print("Timestamp: ", entry[0], " gps", (entry[1],entry[2])," altitude ",entry[3])
    time.sleep(1)