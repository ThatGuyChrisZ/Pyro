import TimelineController from "./timeline.js";
import ThermalOverlay from "./thermal.js";

const fireName = new URLSearchParams(window.location.search).get("name");
const flightId = new URLSearchParams(window.location.search).get("flight_id");

let map, timeline, overlay;
let pathLine = null;
let fullFlightData = [];

// Use Leaflet for overlays
let leafletMap, leafletContainer;

document.addEventListener("DOMContentLoaded", async () => {
  setTitle();
  await initializeMap();
  await initializeOverlay();
  await initializeTimeline();
  await loadFlightPath();
});

function setTitle() {
  const title = document.querySelector("h2");
  if (title) {
    title.textContent = `${fireName} - Flight ${flightId}`;
  }
}

export async function initializeMap() {
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile.bind(protocol));

  const style = {
    version: 8,
    sources: {
      pmtiles_source: {
        type: "vector",
        url: "pmtiles://" + window.location.origin + "/static/tiles/davisfire.pmtiles",
        attribution: "© PMtiles"
      }
    },
    layers: [
      {
        id: "water-fill",
        type: "fill",
        source: "pmtiles_source",
        "source-layer": "water",
        paint: { "fill-color": "#a0c8f0" }
      },
      {
        id: "water-line",
        type: "line",
        source: "pmtiles_source",
        "source-layer": "water",
        paint: {
          "line-color": "#486d99",
          "line-width": 1
        }
      }
    ]
  };

  map = new maplibregl.Map({
    container: "map",
    style: style,
    center: [-119.8325, 52.256195],
    zoom: 0
  });

  leafletContainer = document.createElement("div");
  leafletContainer.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;z-index:10;pointer-events:none";
  document.getElementById("map").appendChild(leafletContainer);

  leafletMap = L.map(leafletContainer, {
    attributionControl: false,
    zoomControl: false,
    zoomSnap: 0,
    scrollWheelZoom: false,
    dragging: false,
    boxZoom: false,
    doubleClickZoom: false,
    touchZoom: false,
    inertia: false
  }).setView([0, 0], 2);

  map.on("move", () => syncLeafletWithMapLibre());
  map.on("zoom", () => syncLeafletWithMapLibre());
  map.once("load", () => syncLeafletWithMapLibre());
}

function syncLeafletWithMapLibre() {
  const center = map.getCenter();
  const zoom = map.getZoom();
  leafletMap.setView([center.lat, center.lng], zoom);
}

async function initializeOverlay() {
  overlay = new ThermalOverlay(leafletMap);
  await overlay.loadThermalData(fireName, null, flightId);
  overlay.render({ fitBounds: true });
}

async function initializeTimeline() {
  const container = document.getElementById("timeline-container");
  if (!container) return;

  timeline = new TimelineController("timeline-container", {
    allowScrubbing: true,
    showTime: true,
    showFlights: false,
  });

  await timeline.loadData(fireName, flightId);

  timeline.onTimeChange(async (timestamp) => {
    if (!timestamp) return;

    const tsNs = new Date(timestamp).getTime() * 1_000_000;

    const partialPoints = fullFlightData
      .filter(pt => pt.time_stamp <= tsNs)
      .map(pt => [pt.lat, pt.lng]);

    if (pathLine && leafletMap.hasLayer(pathLine)) {
      leafletMap.removeLayer(pathLine);
    }

    if (partialPoints.length > 0) {
      pathLine = L.polyline(partialPoints, { color: 'red' }).addTo(leafletMap);
    }

    await overlay.loadThermalData(fireName, timestamp.toISOString(), flightId);
    overlay.render();
  });    
}

async function loadFlightPath() {
  try {
    const res = await fetch(`/api/flights/${encodeURIComponent(fireName)}?flight_id=${flightId}`);
    const data = await res.json();

    fullFlightData = data.wildfire_data.map(pt => ({
      lat: pt.latitude,
      lng: pt.longitude,
      time_stamp: pt.time_stamp
    }));

    leafletMap.fitBounds(L.latLngBounds(fullFlightData.map(p => [p.lat, p.lng])));

    await overlay.loadThermalData(fireName, null, flightId);
    overlay.render();

  } catch (err) {
    console.error("Failed to load flight path:", err);
  }
}