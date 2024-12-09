gps_sim_file = open('sim_gps.txt', 'w')
#alt_sim_file = open('alt_gps.txt', 'r')


starting_lat = 39.5389603
starting_lon = -119.811504
step = 0.0001
for lat in range(0,100):
	for lon in range(0,100):
		starting_lat += step
		gps_sim_file.write(str(starting_lat)+","+str(starting_lon)+"\n")
	starting_lon += 0.0001
	step = step*-1
gps_sim_file.close()
