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

#39.558609, -119.883299
#39.465507, -119.714728

df = pd.DataFrame(
    {
        "City": ["Reno"],
        "Country": ["United States"],
        "Latitude": [me.lat],
        "Longitude": [me.lng],
    }
)

gdf = geopandas.GeoDataFrame(
    df, geometry=geopandas.points_from_xy(df.Longitude, df.Latitude), crs="EPSG:4326"
)

print(gdf.head())

ax = world.clip([39.558609, -119.883299, 39.465507, -119.714728]).plot(color="white", edgecolor="black",aspect=1)

print("Frame info")
print(ax)
#ax = world.clip([left_bound_lat, left_bound_long, -25, 15]).plot(color="white", edgecolor="black")
#gdf.plot(ax=ax, color="red")
plt.show()

