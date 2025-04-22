import time
import math
from database import process_packet
import random

def simulate_flight(
    name: str,
    start_lat: float,
    start_lon: float,
    start_alt: float,
    start_high: float,
    start_low: float,
    session_id: str,
    num_points: int = 100,
    interval: float = 5,
    radius_m: float = 50,
    temp_variation: float = 100
):

    R = 6_371_000
    for i in range(num_points):
        theta = 2 * math.pi * (i / num_points)
        delta_lat = (radius_m / R) * math.cos(theta) * (180 / math.pi)
        delta_lon = (radius_m / R) * math.sin(theta) * (180 / math.pi) / math.cos(start_lat * math.pi/180)

        lat = start_lat + delta_lat
        lon = start_lon + delta_lon

        alt = start_alt + math.sin(theta) * 10 

        high = start_high + random.uniform(0, 400)
        low  = start_low  + random.uniform(-200, 100)

        data = {
            "name":       name,
            "pac_id":     9993 + i,
            "gps_data":   [lat, lon],
            "alt":        alt,
            "high_temp":  high,
            "low_temp":   low,
            "session_id": session_id
        }

        process_packet(data, name, "active")
        print(f"Sent point {i+1}/{num_points}: lat={lat:.6f}, lon={lon:.6f}, high={high:.1f}, low={low:.1f}")

        time.sleep(interval)

if __name__ == "__main__":
    simulate_flight(
        name="test4",
        start_lat=39.292778,
        start_lon=-116.845,
        start_alt=392.4857,
        start_high=324.0185,
        start_low=137.6137,
        session_id="472435352223139",
        num_points=200,
        interval=0.1,
        radius_m=100,
        temp_variation=3
    )
