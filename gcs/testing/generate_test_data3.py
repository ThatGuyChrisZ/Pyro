import json
import random
import math
import datetime


def generate_test_data(
    file_path: str,
    name: str,
    center_lat: float,
    center_lon: float,
    num_flights: int = 5,
    points_per_flight: int = 500,
    background_fraction: float = 0.1,  # points outside fire
    start_date: datetime.datetime = datetime.datetime(2025, 4, 13),
    end_date:   datetime.datetime = datetime.datetime(2025, 4, 20, 23, 59),
    flight_duration_seconds: int = 10 * 60 
):
    """Generate JSON‑lines of synthetic wildfire‑flight packets with evolving fire patterns and background.
    Now produces 5 flights of 500 points each."""
    packets = []
    base_half_range = 0.0125
    base_sigma = 0.005

    base_hotspots = [
        {"lat": center_lat + 0.02,  "lon": center_lon + 0.03, "intensity": 0.9},
        {"lat": center_lat - 0.008, "lon": center_lon + 0.005, "intensity": 0.35},
        {"lat": center_lat - 0.002, "lon": center_lon + 0.02, "intensity": 0.1}
    ]

    total_span = (end_date - start_date).total_seconds()

    for flight_idx in range(num_flights):
        shift_frac = flight_idx / max(1, (num_flights - 1))
        session_time = start_date + datetime.timedelta(seconds=(total_span * shift_frac))
        session_id = str(random.randint(10**14, 10**15 - 1))

        half_range = base_half_range * (1 + shift_frac * 2)
        sigma = base_sigma * (1 + shift_frac * 2)

        hotspots = []
        for h in base_hotspots:
            new_lat = h["lat"] + 0.01 * shift_frac
            new_lon = h["lon"] + 0.01 * shift_frac
            swing = random.uniform(0.5, 1.5)
            new_intensity = min(1.0, h["intensity"] * (1 + 0.5 * shift_frac) * swing)
            hotspots.append({"lat": new_lat, "lon": new_lon, "intensity": new_intensity})

        bg_count = int(points_per_flight * background_fraction)
        core_count = points_per_flight - bg_count

        rows = int(math.sqrt(core_count))
        cols = math.ceil(core_count / rows)
        grid_points = []
        for i in range(rows):
            lat = center_lat - half_range + (2 * half_range) * (i / (rows - 1) if rows > 1 else 0)
            row_pts = []
            for j in range(cols):
                lon = center_lon - half_range + (2 * half_range) * (j / (cols - 1) if cols > 1 else 0)
                row_pts.append((lat, lon))
            if i % 2 == 1:
                row_pts.reverse()
            grid_points.extend(row_pts)
        grid_points = grid_points[:core_count]

        background_points = []
        for _ in range(bg_count):
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(half_range * 1.5, half_range * 2.5)
            lat = center_lat + radius * math.sin(angle)
            lon = center_lon + radius * math.cos(angle)
            background_points.append((lat, lon))

        points = grid_points + background_points

        for idx, (lat, lon) in enumerate(points):
            alt = random.uniform(300, 500)

            if idx < core_count:
                trend = (lon - (center_lon - half_range)) / (2 * half_range)
                base_hi = random.uniform(300, 350) + 200 * (trend - 0.5)
                base_lo = random.uniform(100, 150) + 100 * (trend - 0.5)
            else:
                base_hi = random.uniform(0, 20)
                base_lo = random.uniform(0, 20)

            hi_contrib = lo_contrib = 0
            for h in hotspots:
                d = math.hypot(lat - h["lat"], lon - h["lon"])
                weight = h["intensity"] * math.exp(-(d**2) / (2 * sigma**2))
                hi_contrib += weight * 100
                lo_contrib += weight * 80

            high_temp = base_hi + hi_contrib
            low_temp  = base_lo + lo_contrib

            delta = datetime.timedelta(seconds=(flight_duration_seconds * idx / points_per_flight))
            ts = session_time + delta
            time_stamp = int(ts.timestamp() * 1e9)

            packet = {
                "name":       name,
                "pac_id":     random.randint(1000, 9999),
                "gps_data":   [lat, lon],
                "alt":        alt,
                "high_temp":  high_temp,
                "low_temp":   low_temp,
                "session_id": session_id,
                "time_stamp": time_stamp
            }
            packets.append(packet)

    with open(file_path, "w") as f:
        for pkt in packets:
            f.write(json.dumps(pkt) + "\n")
    print(f"✓ Generated {len(packets)} packets for '{name}', in '{file_path}'")


def merge_files(output_path, input_paths):
    with open(output_path, 'w') as out_f:
        for path in input_paths:
            with open(path, 'r') as in_f:
                out_f.write(in_f.read())


if __name__ == "__main__":
    generate_test_data(
        file_path="davis_fire_packets.jsonl",
        name="Davis Fire",
        center_lat=39.305278,
        center_lon=-119.8325
    )

    generate_test_data(
        file_path="washoe_fire_packets.jsonl",
        name="Washoe Fire",
        center_lat=39.305278,
        center_lon=-116.8325
    )

    merge_files(
        output_path="all_fire_packets.txt",
        input_paths=["davis_fire_packets.jsonl", "washoe_fire_packets.jsonl"]
    )