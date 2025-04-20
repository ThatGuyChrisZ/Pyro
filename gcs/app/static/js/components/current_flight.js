import FlightTimelineController from "./flight_timeline.js";
import ThermalOverlay          from "./thermal.js";

const fireName = new URLSearchParams(window.location.search).get("name");
let flightId     = new URLSearchParams(window.location.search).get("flight_id");

let map, timeline, overlay;
let pathLine, fullFlightData = [];
let lastNs = 0;

const FLIGHT_POLL_INTERVAL = 5000;
const DATA_POLL_INTERVAL   = 2000;

window.addEventListener("DOMContentLoaded", async () => {
  await initializeMap();
  await initializeOverlay();
  await initializeTimeline();
  startPolling();
});

async function initializeMap() {
  const center = await fetchFireCenter();
  map = L.map('map').setView([center.lat, center.lon], 14);

  const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors'
  });
  const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles © Esri'
  });

  osm.addTo(map);

  L.marker([center.lat, center.lon])
   .addTo(map)
   .bindTooltip(fireName)
   .openTooltip();

  document.getElementById('btnMapView')
    .addEventListener('click', () => switchLayer(osm, sat));
  document.getElementById('btnSatelliteView')
    .addEventListener('click', () => switchLayer(sat, osm));
}

function switchLayer(addLayer, removeLayer) {
  if (map.hasLayer(removeLayer)) map.removeLayer(removeLayer);
  if (!map.hasLayer(addLayer))    map.addLayer(addLayer);
  document.getElementById('btnMapView').classList.toggle('active', addLayer === map._layers[Object.keys(map._layers)[1]]);
  document.getElementById('btnSatelliteView').classList.toggle('active', addLayer !== map._layers[Object.keys(map._layers)[1]]);
}

async function initializeOverlay() {
  overlay = new ThermalOverlay(map);
}

async function initializeTimeline() {
  timeline = new FlightTimelineController("timeline-container", {
    allowScrubbing: false,
    showTime:      true
  });
}

// Start polling for flights and data
function startPolling() {
  pollForFlightChange();
  setInterval(pollForFlightChange, FLIGHT_POLL_INTERVAL);
}

// Check for new flight entries
async function pollForFlightChange() {
  try {
    const res = await fetch(
      `/api/live_flight?name=${encodeURIComponent(fireName)}`
    );
    if (!res.ok) return;
    const flights = await res.json();
    if (!flights.length) return;

    const latest = flights
      .reduce((max, f) => Math.max(max, f.flight_id), flights[0].flight_id)
      .toString();

    if (latest !== flightId) {
      flightId = latest;
      resetLiveView();
      pollForData();
      setInterval(pollForData, DATA_POLL_INTERVAL);
    }
  } catch (err) {
    console.error('Flight poll error:', err);
  }
}

// Reset view for a new flight
function resetLiveView() {
  document.querySelector('h2').textContent = `${fireName} – Flight ${flightId} (LIVE)`;
  fullFlightData = [];
  lastNs = 0;

  if (pathLine) {
    map.removeLayer(pathLine);
    pathLine = null;
  }
  overlay.reset();
  timeline.clear();
}

// Poll for new data
async function pollForData() {
  try {
    const res = await fetch(
      `/api/live_flight?name=${encodeURIComponent(fireName)}`
      + `&flight_id=${flightId}`
      + `&after=${lastNs}`
    );
    if (!res.ok) return;

    const { wildfire_data } = await res.json();
    for (const pt of wildfire_data) {
      lastNs = Math.max(lastNs, pt.time_stamp);
      const ts = new Date(pt.time_stamp / 1e6);
      appendToMapAndOverlay(ts, pt.latitude, pt.longitude, [pt.high_temp, pt.low_temp]);
    }
  } catch (err) {
    console.error('Data poll error:', err);
  }
}

// Append new point to map, overlay, and timeline
function appendToMapAndOverlay(ts, lat, lng, temps) {
  fullFlightData.push({ ts, lat, lng, temperatures: temps });

  if (!pathLine) {
    pathLine = L.polyline([[lat, lng]], { color: 'red' }).addTo(map);
    map.panTo([lat, lng]);
  } else {
    pathLine.addLatLng([lat, lng]);
    map.panTo([lat, lng], { animate: false });
  }

  overlay.appendPoint(lat, lng, temps);
  timeline.addPoint(ts);
}