import pygmt
pygmt.show_versions()

fig = pygmt.Figure()
fig.coast(region="g", frame=True, shorelines=1)
fig.show()