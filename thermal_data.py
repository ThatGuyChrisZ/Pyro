class thermal_data:
  def __init__(self, frame):
    self.max_temp = max(frame)
    self.min_temp = min(frame)
    self.array = frame
