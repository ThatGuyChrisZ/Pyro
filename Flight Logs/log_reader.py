import subprocess

# Call U log to csv
file = "log_0_2025-3-21-15-48-50.ulg"
log_path = "C:/Users/warbr/Documents/GitHub/Pyro/Flight Logs/" + file

subprocess.call(['ulog2csv', log_path])