import json
import random
import math
import datetime

def generate_washoe_fire_data(
    file_path: str = "washoe_fire_packets.txt",
    name: str = "Washoe Fire",
    center_lat: float = 39.305278,
    center_lon: float = -116.8325,
    num_flights: int = 10,
    points_per_flight: int = 500,
    background_fraction: float = 0.1,
    start_date: datetime.datetime = None,
    end_date: datetime.datetime = None,
    flight_duration_seconds: int = 10 * 60
):
    
    now = datetime.datetime.now()
    if end_date is None:
        end_date = now
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=3)

    base_hotspot = {
        "lat": center_lat + 0.0,
        "lon": center_lon + 0.02,
        "intensity": 1.0
    }

    base_half_range = 0.003  
    base_sigma = 0.002      

    packets = []
    total_seconds = (end_date - start_date).total_seconds()

    for flight_idx in range(num_flights):
        shift_frac = flight_idx / max(1, num_flights - 1)
        session_time = start_date + datetime.timedelta(seconds=total_seconds * shift_frac)
        growth = shift_frac 

        half_range = base_half_range * (1 + growth * 3)
        sigma = base_sigma * (1 + growth * 2)

        hotspot = {
            "lat": base_hotspot["lat"] + random.uniform(-0.001, 0.001),
            "lon": base_hotspot["lon"] + random.uniform(-0.001, 0.001),
            "intensity": base_hotspot["intensity"] * growth
        }

        core_count = points_per_flight - int(points_per_flight * background_fraction)
        rows = int(math.sqrt(core_count)) or 1
        cols = math.ceil(core_count / rows)
        grid = []
        for r in range(rows):
            lat = center_lat - half_range + (2 * half_range) * (r / (rows - 1) if rows>1 else 0)
            row_pts = []
            for c in range(cols):
                lon = center_lon - half_range + (2 * half_range) * (c / (cols - 1) if cols>1 else 0)
                row_pts.append((lat, lon))
            if r % 2 == 1:
                row_pts.reverse()
            grid.extend(row_pts)
        core_points = grid[:core_count]

        bg_points = []
        bg_count = int(points_per_flight * background_fraction)
        for _ in range(bg_count):
            angle = random.uniform(0, 2*math.pi)
            radius = random.uniform(half_range*1.5, half_range*2.5)
            bg_points.append((
                center_lat + radius * math.sin(angle),
                center_lon + radius * math.cos(angle)
            ))

        all_points = core_points + bg_points

        for idx, (lat, lon) in enumerate(all_points):
            alt = random.uniform(300, 500)
            if idx < core_count:
                base_hi = random.uniform(50, 100) * growth
                base_lo = random.uniform(20, 50) * growth
            else:
                base_hi = random.uniform(0, 20)
                base_lo = random.uniform(0, 20)

            d = math.hypot(lat - hotspot["lat"], lon - hotspot["lon"])
            weight = hotspot["intensity"] * math.exp(- (d**2) / (2 * sigma**2))
            hi_contrib = weight * 300
            lo_contrib = weight * 200

            high_temp = base_hi + hi_contrib
            low_temp  = base_lo + lo_contrib

            delta = datetime.timedelta(seconds=(flight_duration_seconds * idx / points_per_flight))
            ts = session_time + delta
            time_stamp = int(ts.timestamp() * 1e9)

            packets.append({
                "name": name,
                "pac_id": random.randint(100000, 999999),
                "gps_data": [lat, lon],
                "alt": alt,
                "high_temp": high_temp,
                "low_temp": low_temp,
                "session_id": f"{name.replace(' ', '')}_{flight_idx}_{int(session_time.timestamp())}",
                "time_stamp": time_stamp
            })

    with open(file_path, "w") as f:
        for pkt in packets:
            f.write(json.dumps(pkt) + "\n")

    print(f"✓ Generated {len(packets)} packets for '{name}' in '{file_path}'")


if __name__ == "__main__":
    generate_washoe_fire_data()
