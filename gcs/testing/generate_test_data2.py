import json
import random
import math

def generate_test_data(file_path, name, center_lat, center_lon, num_points=100):
    packets = []
    half_range = 0.0125

    session_id_1 = str(random.randint(10**14, 10**15 - 1))
    session_id_2 = str(random.randint(10**14, 10**15 - 1))

    # Hotspots on the Map
    hotspots = [
        {"lat": center_lat + 0.02, "lon": center_lon + 0.03, "intensity": 0.9},
        {"lat": center_lat - 0.008, "lon": center_lon + 0.005, "intensity": 0.35},
        {"lat": center_lat - 0.002, "lon": center_lon + 0.02, "intensity": 0.1}
    ]

    sigma = 0.005
    rows = int(math.sqrt(num_points))
    cols = math.ceil(num_points / rows)
    
    # Generate grid points as if drone is flying in snake pattern
    points = []
    for i in range(rows):
        lat = center_lat - half_range + (i / (rows - 1)) * (2 * half_range) if rows > 1 else center_lat
        row_points = []
        for j in range(cols):
            lon = center_lon - half_range + (j / (cols - 1)) * (2 * half_range) if cols > 1 else center_lon
            row_points.append((lat, lon))
        if i % 2 == 1:
            row_points.reverse()
        points.extend(row_points)
    
    points = points[:num_points]
    
    # Create a packet for each point.
    for index, (lat, lon) in enumerate(points):
        alt = random.uniform(300, 500)

        trend_factor = (lon - (center_lon - half_range)) / (2 * half_range)
        base_high_temp = random.uniform(300, 350) + trend_factor * 50
        base_low_temp  = random.uniform(100, 150) + trend_factor * 30
        
        hotspot_high_contrib = 0
        hotspot_low_contrib = 0
        
        for hotspot in hotspots:
            d = math.sqrt((lat - hotspot["lat"])**2 + (lon - hotspot["lon"])**2)
            contrib = hotspot["intensity"] * math.exp(- (d ** 2) / (2 * sigma ** 2))
            hotspot_high_contrib += contrib * 100 
            hotspot_low_contrib  += contrib * 80  
        
        high_temp = base_high_temp + hotspot_high_contrib
        low_temp  = base_low_temp  + hotspot_low_contrib

        # Assign session_id based on packet index
        session_id = session_id_1 if index < num_points // 2 else session_id_2

        packet = {
            "name": name,
            "pac_id": random.randint(1000, 9999),
            "gps_data": [lat, lon],
            "alt": alt,
            "high_temp": high_temp,
            "low_temp": low_temp,
            "session_id": session_id,
        }
        packets.append(packet)
    
    with open(file_path, 'w') as file:
        for packet in packets:
            file.write(json.dumps(packet) + '\n')
    
    print(f"Generated {len(packets)} packets for '{name}' and saved to {file_path}")
    print(f"Session 1: {session_id_1}, Session 2: {session_id_2}")

generate_test_data(
    file_path='test_packets.txt',
    name='Washoe Fire',
    center_lat=39.305278,
    center_lon=-116.8325,
    num_points=1000
)