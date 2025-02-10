# ///////////////////////////////////////////////////
# contributed by Robb Northrup
# ///////////////////////////////////////////////////

import struct # For serialization of the data
import time
MAX_SEND_TIMEOUT_SEC = 1.5e10 # 15 Seconds

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
    
    def check_timeout(self):
        if time.time_ns() < self.req_ack_time:
            return False
        else:
            return True