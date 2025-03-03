########################################################################
#   Function Name: thermal_data                                        #
#   Author: Chris Zinser                                               #
#   Paramters: queue                                                   #
#   Description: This data structure provides an organized format      #
#                for information collected by the pi's perephials.     #
#                Allowing further modification and transmission of     #
#                sensor data to be quick and easy to implement         #
#   Return: None                                                       #
########################################################################
class thermal_data:
    def Retrieve_Flight_Data(self):
        self.gps = (34.246,25.7899)
        self.barometric = 1200
        self.compass = 0.00
        
    def __init__(self, frame):
        self.max_temp = int(max(frame))
        self.min_temp = int(min(frame))
        self.gps =(0.00,0.00)
        self.barometric = 0
        self.compass = 0.00
        self.array = frame
