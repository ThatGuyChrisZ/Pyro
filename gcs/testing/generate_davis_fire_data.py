import json
import random
import math
import datetime

def generate_davis_fire_data(
    file_path: str = "davis_fire_packets.txt",
    name: str = "Davis Fire",
    center_lat: float = 39.305278,
    center_lon: float = -119.8325,
    num_flights: int = 50,
    min_points: int = 100,
    max_points: int = 1000,
    background_fraction: float = 0.1,
    start_date: datetime.datetime = None,
    end_date: datetime.datetime = None,
    flight_duration_seconds: int = 10 * 60
):
    """Generate JSON-lines of synthetic wildfire-flight packets for Davis Fire over one week."""
    now = datetime.datetime.now()
    if end_date is None:
        end_date = now
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=7)

    base_half_range = 0.005 
    base_sigma = base_half_range / 2

    # Base hotspot definitions relative to fire center
    base_hotspots = [
        {"lat": center_lat + 0.01,  "lon": center_lon + 0.02,  "intensity": 1.0},
        {"lat": center_lat - 0.012, "lon": center_lon + 0.015, "intensity": 0.8},
        {"lat": center_lat + 0.0,   "lon": center_lon - 0.02,  "intensity": 0.6},
    ]

    packets = []
    total_seconds = (end_date - start_date).total_seconds()

    for flight_idx in range(num_flights):
        shift_frac = flight_idx / max(1, num_flights - 1)
        session_time = start_date + datetime.timedelta(seconds=total_seconds * shift_frac)
        growth_factor = math.sin(math.pi * shift_frac)

        half_range = base_half_range * (1 + growth_factor * 4)
        sigma = base_sigma * (1 + growth_factor * 4)

        hotspots = []
        for h in base_hotspots:
            jitter_lat = random.uniform(-0.001, 0.001)
            jitter_lon = random.uniform(-0.001, 0.001)
            hotspots.append({
                "lat": h["lat"] + jitter_lat,
                "lon": h["lon"] + jitter_lon,
                "intensity": h["intensity"] * growth_factor
            })

        num_points = random.randint(min_points, max_points)
        bg_count = int(num_points * background_fraction)
        core_count = num_points - bg_count

        core_points = [
            (
                center_lat + random.uniform(-half_range, half_range),
                center_lon + random.uniform(-half_range, half_range)
            )
            for _ in range(core_count)
        ]

        # Background survey points (low-temp)
        background_points = []
        for _ in range(bg_count):
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(half_range * 1.5, half_range * 2.5)
            background_points.append((
                center_lat + radius * math.sin(angle),
                center_lon + radius * math.cos(angle)
            ))

        all_points = core_points + background_points
        random.shuffle(all_points)

        for idx, (lat, lon) in enumerate(all_points):
            alt = random.uniform(300, 500)
            if idx < core_count:
                base_hi = random.uniform(200, 300) * growth_factor
                base_lo = random.uniform(100, 150) * growth_factor
            else:
                base_hi = random.uniform(0, 20)
                base_lo = random.uniform(0, 20)

            hi_contrib = lo_contrib = 0.0
            for h in hotspots:
                d = math.hypot(lat - h["lat"], lon - h["lon"])
                weight = h["intensity"] * math.exp(- (d ** 2) / (2 * sigma ** 2))
                hi_contrib += weight * 200
                lo_contrib += weight * 150

            high_temp = base_hi + hi_contrib
            low_temp = base_lo + lo_contrib

            delta = datetime.timedelta(seconds=(flight_duration_seconds * idx / num_points))
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
    generate_davis_fire_data()
