import math
from typing import List, Dict


class DataPoint:
    def __init__(self, fire_name: str, latitude: float, longitude: float, temperature: float, date: str, time = float):
        self.fire_name = fire_name
        self.latitude = latitude
        self.longitude = longitude
        self.temperature = temperature
        self.date = date
        self.time = time


class DroneData:
    def __init__(self):
        self.data_points: List[DataPoint] = []

    def add_data_point(self, fire_name: str, latitude: float, longitude: float, temperature: float, date: str, time = float):
        self.data_points.append(DataPoint(fire_name, latitude, longitude, temperature, date, time))

    def get_average_temperature(self) -> float:
        if not self.data_points:
            return 0.0
        return sum(dp.temperature for dp in self.data_points) / len(self.data_points)


def calculate_frame_size(height: float, fov: float = 55.0) -> float:
    fov_radians = math.radians(fov)
    return 2 * height * math.tan(fov_radians / 2)


def prepare_heatmap_data(drone_data: DroneData) -> List[Dict]:
    return [
        {"lat": dp.latitude, "lon": dp.longitude, "temp": dp.temperature, "fire_name": dp.fire_name}
        for dp in drone_data.data_points
    ]