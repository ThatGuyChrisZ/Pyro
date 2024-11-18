import csv
import random
from datetime import datetime, timedelta

def generate_test_data(csv_file_path, fire_name, center_lat, center_lon, num_points=100):

    with open(csv_file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["name", "latitude", "longitude", "temperature", "date", "time", "status"])
        
        for _ in range(num_points):
            lat = center_lat + random.uniform(-0.01, 0.01)
            lon = center_lon + random.uniform(-0.01, 0.01) 
            
            temperature = random.uniform(300, 500)
            
            date_time = datetime.now() - timedelta(days=random.randint(0, 7), seconds=random.randint(0, 86400))
            date = date_time.strftime('%Y-%m-%d')
            time = date_time.strftime('%H:%M:%S')

            status = "active"
            
            writer.writerow([fire_name, lat, lon, temperature, date, time, status])
    
    print(f"Generated {num_points} data points for '{fire_name}' and saved to {csv_file_path}")

generate_test_data(
    csv_file_path='testdata.csv',
    fire_name='Davis Fire',
    center_lat=39.305278,
    center_lon=-119.8325,
    num_points=500
)
