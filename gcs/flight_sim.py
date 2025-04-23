import time
import math
import random
from database import process_packet

def simulate_flight(
    name: str,
    center_lat: float,
    center_lon: float,
    start_alt: float,
    start_high: float,
    start_low: float,
    session_id: str,
    num_points: int = 500,
    interval: float = 0.1,
    half_range: float = 0.005,
    sigma: float = 0.003,
    hotspot_strength: float = 1.0,
    jitter_frac: float = 0.02  
):
    
    base_hotspots = [
        {"lat": center_lat + 0.02,  "lon": center_lon + 0.03, "intensity": 0.9},
        {"lat": center_lat - 0.008, "lon": center_lon + 0.005, "intensity": 0.6},
        {"lat": center_lat - 0.002, "lon": center_lon + 0.02,  "intensity": 0.4}
    ]

    v0 = (center_lat - half_range, center_lon - half_range)  # SW
    v1 = (center_lat - half_range, center_lon + half_range)  # SE
    v2 = (center_lat + half_range, center_lon + half_range)  # NE
    v3 = (center_lat + half_range, center_lon - half_range)  # NW
    verts = [v0, v1, v2, v3, v0]

    seg_lengths = []
    total_len = 0.0
    for a, b in zip(verts, verts[1:]):
        d = math.hypot(b[0]-a[0], b[1]-a[1])
        seg_lengths.append(d)
        total_len += d

    points = []
    for i in range(num_points):

        dist = (i / num_points) * total_len
        acc = 0.0
        for (a, b), seg_len in zip(zip(verts, verts[1:]), seg_lengths):
            if acc + seg_len >= dist:
                frac = (dist - acc) / seg_len
                lat = a[0] + frac * (b[0] - a[0])
                lon = a[1] + frac * (b[1] - a[1])
                points.append((lat, lon))
                break
            acc += seg_len

    jitter = half_range * jitter_frac

    for idx, (lat0, lon0) in enumerate(points, start=1):
        lat = lat0 + random.uniform(-jitter, jitter)
        lon = lon0 + random.uniform(-jitter, jitter)

        alt = start_alt + random.uniform(-5, 5)

        base_hi = start_high + random.uniform(-5, 5)
        base_lo = start_low  + random.uniform(-5, 5)

        hi_contrib = lo_contrib = 0.0
        for h in base_hotspots:
            d = math.hypot(lat - h["lat"], lon - h["lon"])
            w = h["intensity"] * math.exp(-(d**2)/(2*sigma**2))
            hi_contrib += w * hotspot_strength * 600
            lo_contrib += w * hotspot_strength * 450

        high_temp = base_hi + hi_contrib
        low_temp  = base_lo + lo_contrib

        packet = {
            "name":       name,
            "pac_id":     random.randint(1000, 9999),
            "gps_data":   [lat, lon],
            "alt":        alt,
            "high_temp":  high_temp,
            "low_temp":   low_temp,
            "session_id": session_id
        }
        process_packet(packet, name, "active")

        print(f"[{idx:4d}/{num_points}] "
              f"lat={lat:.6f}, lon={lon:.6f}, "
              f"alt={alt:.1f}, hi={high_temp:.1f}, lo={low_temp:.1f}")

        time.sleep(interval)


if __name__ == "__main__":
    simulate_flight(
        name="Test Fire",
        center_lat=39.292778,
        center_lon=-116.845000,
        start_alt=392.5,
        start_high=324.0,
        start_low=137.6,
        session_id="DRONE20250423",
        num_points=800,       
        interval=0.05,        
        half_range=0.005,     
        sigma=0.003,
        hotspot_strength=1.0,
        jitter_frac=0.02
    )
