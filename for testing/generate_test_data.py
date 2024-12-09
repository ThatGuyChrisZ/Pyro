import json
import random
from datetime import datetime, timedelta


def generate_test_data(file_path, name, center_lat, center_lon, num_points=100):
    packets = []

    for _ in range(num_points):
        lat = center_lat + random.uniform(-0.01, 0.01)
        lon = center_lon + random.uniform(-0.01, 0.01)
        alt = random.uniform(500, 1500)
        high_temp = random.uniform(400, 500)
        low_temp = random.uniform(300, 399)

        packet = {
            "name": name,
            "pac_id": random.randint(1000, 9999),
            "gps_data": [lat, lon],
            "alt": alt,
            "high_temp": high_temp,
            "low_temp": low_temp,
        }
        packets.append(packet)

    with open(file_path, 'w') as file:
        for packet in packets:
            file.write(json.dumps(packet) + '\n')

    print(f"Generated {num_points} packets for '{name}' and saved to {file_path}")

generate_test_data(
    file_path='test_packets.txt',
    name='Peak Fire',
    center_lat=38.15168,
    center_lon=-118.55576,
    num_points=500
)