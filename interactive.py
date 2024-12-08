import geopandas
import geodatasets
import sys
from PyQt5.QtCore import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QApplication

#nybb = geopandas.read_file(geodatasets.get_path("nybb"))
#chicago = geopandas.read_file(geodatasets.get_path("geoda.chicago_commpop"))
#groceries = geopandas.read_file(geodatasets.get_path("geoda.groceries")).explode(ignore_index=True)

#nybb.explore(
#    column="BoroName",  # make choropleth based on "BoroName" column
#    tooltip="BoroName",  # show "BoroName" value in tooltip (on hover)
#    popup=True,  # show all values in popup (on click)
#    tiles="CartoDB positron",  # use "CartoDB positron" tiles
#    cmap="Set1",  # use "Set1" matplotlib colormap
#    style_kwds=dict(color="black"),  # use black outline
#)

import folium

m = folium.Map(location=(39.534120, -119.791632))
#groceries.explore(
#    m=m,  # pass the map object
#   color="red",  # use red color on all points
#    marker_kwds=dict(radius=5, fill=True),  # make marker radius 10px with fill
#    tooltip="Address",  # show "name" column in the tooltip
#    tooltip_kwds=dict(labels=False),  # do not show column label in the tooltip
#    name="groceries",  # name of the layer in the map
#)

#folium.TileLayer("CartoDB positron", show=False).add_to(
#    m
#)  # use folium to add alternative tiles
#folium.LayerControl().add_to(m)  # use folium to add layer control

m  # show map
m.save("index.html")


app = QApplication(sys.argv)

web = QWebEngineView()
web.load(QUrl("https://www.google.com"))
web.show()

sys.exit(app.exec_())