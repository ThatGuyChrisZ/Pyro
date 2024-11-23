import pandas as pd
import geopandas
import matplotlib.pyplot as plt
from geodatasets import get_path
import geocoder

me = geocoder.ip('me')


print("Booting Visualization")
print(me.latlng)

#left_bound_lat = me.lat - 10
#right_bound_lat = me.lat + 10
#left_bound_long = me.lng - 10
#right_bound_long = me.lng + 10

world = geopandas.read_file(get_path("naturalearth.land"))
#ax = world.clip([-90, -55, -25, 15]).plot(color="white", edgecolor="black")

ax = world.clip([left_bound_lat, left_bound_long, -25, 15]).plot(color="white", edgecolor="black")
#gdf.plot(ax=ax, color="red")
plt.show()

