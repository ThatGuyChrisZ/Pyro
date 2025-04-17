import subprocess
import time
import random
import matplotlib
import pylab as plt
from pyulog import ULog
file = "hex.ulg"
log_path = "C:/Users/warbr/Documents/GitHub/Pyro/Flight Logs/" + file

subprocess.call(['ulog2csv','-o','.\output', log_path])
#subprocess.call(['ulog2kml', log_path])

log_file = ULog(log_path)
flight_data = []
alt_data = []


for data in log_file.data_list:
         print(f"Message Name: {data.name}")
#        #print(f"Number of data points: {len(data.data['timestamp'])}")
#        #print(f"Timestamps: {data.data['timestamp'][:10]}")
         if data.name == 'sensor_combined':
              print(data.data)
         if data.name == 'estimator_attitude':
              print(data.data)
         if data.name == 'mission':
            print(data.data)
         if data.name == 'vehicle_air_data':
              print(data.data['baro_alt_meter'])
              count = 0
              for entry in data.data:
                alt_data.append(data.data['baro_alt_meter'][count])
                count = count+1
                
         print("Alt List Length ",  len(alt_data))  
         if data.name == 'vehicle_global_position':
            print(data.data)

         if data.name == 'sensor_baro':
             print(data.data)  
         if  data.name == 'vehicle_gps_position':
            print(data.data)
            print("timestamp")
            print(data.data['timestamp'])
            print("latitude")
            print(data.data['lat'])
            print("longitude")
            print(data.data['lon'])
            print("altitude")
            print(data.data['alt'])
            print("Alt Data Length: ", len(data.data))
            print("GPS Data Length: ", len(data.data))
            count = 0
            weighted_random = 0
            for entry in data.data:
                  timestamp = data.data['timestamp'][count]
                  lat = data.data['lat'][count]
                  lon = data.data['lon'][count]
                  alt = alt_data[count]
                  print("Alt:",alt)
                  flight_data.append((timestamp,lat,lon,alt))
                  count+=1

                  random.randint(0,100)
                  if weighted_random >0:
                        sim_temp = random.randint(300,400)
                        weighted_random = weighted_random -1
                  else:
                        sim_temp = random.randint(0,70)
                
                  fate = random.randint(0,100)

                  if fate < 5:
                        weighted_random = 5
                        

                  
#            #print(f"vehicle_gps_position values: {data.data['vehicle_gps_position'][:10]}")
print("Flight Data:")
#print(flight_data)


print("beginning Sim: ") 



import matplotlib.pyplot as plt
import random

plt.ion()  # turning interactive mode on

# preparing the data
y = [0]
x = [0]

# plotting the first frame
graph = plt.plot(x,y)[0]
plt.ylim(0,50)
plt.pause(1)
initial_alt = flight_data[0][3]/1000

# the update loop
count = 0
print(len(flight_data))
while(True):

    if count < len(flight_data):
        # updating the data
        #y.append(flight_data[count][3])
        #x.append(flight_data[count][0]/1000/1000)
        print(count)
        print(initial_alt)
        print(flight_data[count][3]/1000 - initial_alt)
        y.append(flight_data[count][3]/1000 - initial_alt)
        x.append(x[-1]+1)
    
        # removing the older graph
        graph.remove()
    
        # plotting newer graph
        graph = plt.plot(x,y,color = 'g')[0]
        plt.xlim(x[0], x[-1])
    
        # calling pause function for 0.25 seconds
        count+=1
        plt.pause(1)