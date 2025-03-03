def combineData(packet, file_path):

    radioPacket = {
        "pac_id": packet.pac_id,
        "gps_data": packet.gps_data,
        "alt": packet.alt,
        "high_temp": packet.high_temp,
        "low_temp": packet.low_temp,
        "time": packet.time
    }

    try:
        with open(file_path, 'r') as file:
            new_data = json.load(file)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing JSON file: {e}")
        return

    if not isinstance(radioPacket, dict) or not isinstance(new_data, dict):
        raise ValueError("Both packet and new_data must be dictionaries.")

    combined_packet = radioPacket.copy()
    combined_packet.update(new_data)
    return combined_packet