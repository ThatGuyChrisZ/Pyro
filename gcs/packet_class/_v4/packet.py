# ///////////////////////////////////////////////////
# contributed by Robb Northrup
# ///////////////////////////////////////////////////

# DESCRIPTION:
# V4 updates the radio protocol to only send temperature data
# alongside a timestamp (and the packet ID) to the GCS from the
# ridealong board. Information is then synced up on the GCS end,
# where telemetry data is pulled from mission planner and synced
# with these packets


import struct # For serialization of the data
import zlib # checksum/error detection
import time
MAX_SEND_TIMEOUT_SEC = 1.0e10 # 10 Second timeout



########################################################################
#   Class Name: Packet                                                 #
#   Author: Robb Northrup                                              #
#   Parameters: pac_id<int>, gps_data<[float, float]>, alt<int>,       #
#               high_temp<short>, low_temp<short>                      #                               
#   Description: Simple data structure for holding all related         #
#                information to a thermal frame for serialization,     #
#                and then transmission to the GCS                      #
########################################################################
class Packet:
    def __init__(self, pac_id, gps_data, alt, high_temp, low_temp, time_stamp):
        self.pac_id = pac_id
        self.gps_data = gps_data # This should be a list of two floats, [lat, long]
        self.alt = alt # Altitude in meters
        self.high_temp = high_temp # Highest temp in cel, of frame
        self.low_temp = low_temp # Lowest temp in cel, of frame
        self.time_stamp = time_stamp # long long (in64): This is the time (recorded from the Raspberry Pi) when the information was pulled from the sensors

    def serialize(self):
        # The format of the payload is as follows: int, float, float, int, short, short, long long
        # Updated to include 'q' to include the long long as a timestamp
        # '<' little endian encoded
        payload = struct.pack('<IffIhhq', \
            self.pac_id, \
            self.gps_data[0], \
            self.gps_data[1], \
            self.alt, \
            self.high_temp, \
            self.low_temp, \
            self.time_stamp)
        checksum = zlib.crc32(payload)

        serialized_data = payload + struct.pack('<I', checksum)  # Append checksum as unsigned int

        return serialized_data
    
    def deserialize(self):
        # IMPLEMENT MEEEEEEEEEEEEEEEEEEEEE!!!!!!!!!!!!
        pass

    def __str__(self):
        return f"         ======================\n \
             PACKET #{self.pac_id}\n \
        ======================\n \
            PACKET ID - {self.pac_id}\n \
            GPS COORDINATES - {self.gps_data}\n \
            ALTITUDE - {self.alt}\n \
            HIGH TEMP - {self.high_temp}\n \
            LOW TEMP - {self.low_temp}\n \
            TIME STAMP - {self.time_stamp}"



########################################################################
#   Class Name: Packet_Info                                            #
#   Author: Robb Northrup                                              #
#   Parameters: serialized_packet<serialized packet>, pac_id<int>      #                            
#   Description: This class holds metadata (time_sent, pac_id,         #
#                req_ack_time, serialized_packet) for the purposes     #
#                storing this information in an array in the case      #
#                of a required selective repeat transmission in the    #
#                handshake method.                                     #
########################################################################
class Packet_Info:
    def __init__(self, serialized_packet, pac_id):
        self.serialized_packet = serialized_packet
        self.pac_id = pac_id

        self.sent_time = None
        self.req_ack_time = None

    def set_timestamp(self, sent_time):
        self.sent_time = sent_time
        self.req_ack_time = self.sent_time + MAX_SEND_TIMEOUT_SEC

    def get_timestamp(self):
        return self.sent_time
    
    def get_pac_id(self):
        return self.pac_id
    
    def check_timeout(self):
        if time.time_ns() < self.req_ack_time:
            return False
        else:
            return True
        


########################################################################
#   Class Name: Packet_Info_Dict                                       #
#   Author: Robb Northrup                                              #
#   Parameters: packet_info_instance<Packet_Info>                      #                            
#   Description: A wrapper for a dictionary that include metadata      #
#                for packets in the queue waiting for possible         #
#                retransmission                                        #
########################################################################
class Packet_Info_Dict:
    def __init__(self, packet_info_instance=None):
        self.master_dictionary = dict()

        if packet_info_instance != None:
            self.master_dictionary[packet_info_instance.pac_id] = packet_info_instance

    def access(self, pac_id):
        return self.master_dictionary[pac_id]
    
    def peek_top_packet_info(self):
        # Could be implemented better, possible store top_key with metadata of the class?
        top_key = next(iter(self.master_dictionary))  # Get the first key
        return self.master_dictionary[top_key]  # Return top Packet_Info
    
    def peek_top_pac_id(self):
        # Could be implemented better, possible store top_key with metadata of the class?
        return next(iter(self.master_dictionary))  # Return the first key (pac_id)
    
    def check_top_timeout(self):
        if self.is_empty():
            return False
        else:
            top_packet_info = self.peek_top_packet_info()
            return top_packet_info.check_timeout()

    def contains(self, pac_id):
        if pac_id in self.master_dictionary:
            return True
        else:
            return False

    def add(self, packet_info_instance):
        self.master_dictionary[packet_info_instance.pac_id] = packet_info_instance

    def pop(self, pac_id):
        if self.contains(pac_id):
            self.master_dictionary.pop(pac_id)
        else:
            pass

    def is_empty(self):
        if len(self.master_dictionary) == 0:
            return True
        else:
            return False
