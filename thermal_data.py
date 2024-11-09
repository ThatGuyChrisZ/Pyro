class thermal_data:
    def Retrieve_Flight_Data(self):
        self.gps = (34.246,25.7899)
        self.barometric = 1200
        self.compass = 0.00
        
    def __init__(self, frame):
        self.max_temp = max(frame)
        self.min_temp = min(frame)
        self.gps =(0.00,0.00)
        self.barometric = 0
        self.compass = 0.00
        self.array = frame
    
