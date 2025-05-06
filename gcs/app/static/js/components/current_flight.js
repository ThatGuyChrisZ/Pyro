import ThermalOverlay from "./thermal.js";

const params        = new URLSearchParams(window.location.search);
const fireName      = params.get("name");
const rawFlightId   = params.get("flight_id");

// treat "null" or empty as no flight selected
const flightId      = rawFlightId && rawFlightId !== "null" ? rawFlightId : null;

const DATA_INTERVAL = 2000;  

let map, overlay, pathLine;
let lastTimestamp   = 0;
let dataTimer;
let knownFlightId   = 0;

document.addEventListener("DOMContentLoaded", async () => {
  setTitle();

  // Waiting for a new flight
  if (!flightId) {
    await fetchExistingFlights();
    pollForNewFlight();
    return;
  }

  // Live flight mode
  await initializeMap();
  overlay = new ThermalOverlay(map, {
    mode: "flight",
    recentWindowHours: 12,
    minHighTemp: 0
  });
  await loadFlightPath();
  startDataPolling();
});

// Set title based on user given fire name
function setTitle() {
  const title = document.querySelector("h2");
  if (!title) return;
  if (flightId) {
    title.textContent = `${fireName} – Flight ${flightId} (LIVE)`;
  } else {
    title.textContent = `${fireName} – Awaiting new flight…`;
  }
}

function flightsURL() {
  return `/api/flights/${encodeURIComponent(fireName)}`;
}

function thermalURL() {
  const base = `/api/thermal/${encodeURIComponent(fireName)}`;
  return flightId
    ? `${base}?flight_id=${encodeURIComponent(flightId)}`
    : base;
}

// Find most recent flight ID
async function fetchExistingFlights() {
  const res     = await fetch(flightsURL(), { cache: "no-store" });
  const flights = await res.json();
  const ids     = flights.map(f => f.flight_id ?? f.id);
  knownFlightId = ids.length ? Math.max(...ids) : 0;
}

// Queries for a new flight every 2s
function pollForNewFlight() {
  setInterval(async () => {
    const res     = await fetch(flightsURL(), { cache: "no-store" });
    const flights = await res.json();
    const ids     = flights.map(f => f.flight_id ?? f.id);
    const maxId   = ids.length ? Math.max(...ids) : 0;

    if (maxId > knownFlightId) {
      const url = new URL(window.location.href);
      url.searchParams.set("flight_id", maxId);
      window.location.replace(url);
    }
  }, DATA_INTERVAL);
}

// Add new datapoint to the thermalOverlay object
function appendPoint(lat, lng, temps, altitude = null, timestamp = null) {
  const [highTemp, lowTemp] = temps;
  const rawTemp = (highTemp + lowTemp) / 2;

  overlay.thermalData = overlay.thermalData || [];
  overlay.thermalData.push({ lat, lng, rawTemp, altitude, timestamp });

  const rawTemps = overlay.thermalData.map(pt => pt.rawTemp);
  const minTemp  = Math.min(...rawTemps);
  const maxTemp  = Math.max(...rawTemps);

  overlay.thermalData.forEach(pt => {
    pt.intensity = maxTemp > minTemp
      ? (pt.rawTemp - minTemp) / (maxTemp - minTemp)
      : 1;
  });

  const altitudes = overlay.thermalData.map(pt => pt.altitude || 0);
  overlay.avgAltitude = altitudes.reduce((sum, a) => sum + a, 0) / altitudes.length;
}


async function initializeMap() {
  const center   = await fetchFireCenter();
  const container = document.getElementById("map");

  // destroy any existing map instance
  if (map) {
    map.off();
    map.remove();
  }
  container.innerHTML = "";
  delete container._leaflet_id;

  map = L.map(container).setView([center.lat, center.lon], 14);

  const osm = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 18, attribution: "© OpenStreetMap contributors" }
  ).addTo(map);

  const sat = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles © Esri" }
  );

  document.getElementById("btnMapView")
    .addEventListener("click", () => {
      map.removeLayer(sat); map.addLayer(osm);
      toggleActive("btnMapView", "btnSatelliteView");
    });
  document.getElementById("btnSatelliteView")
    .addEventListener("click", () => {
      map.removeLayer(osm); map.addLayer(sat);
      toggleActive("btnSatelliteView", "btnMapView");
    });

  L.marker([center.lat, center.lon])
    .addTo(map)
    .bindTooltip(fireName || "Unknown Fire")
    .openTooltip();
}

function toggleActive(onId, offId) {
  document.getElementById(onId).classList.add("active");
  document.getElementById(offId).classList.remove("active");
}

// Returns fire center from wildfire_markers API endpoint
async function fetchFireCenter() {
  try {
    const res = await fetch("/wildfire_markers?filter=active");
    const arr = await res.json();
    const f   = arr.find(x => x.name === fireName);
    return f
      ? { lat: f.avg_latitude, lon: f.avg_longitude }
      : { lat: 39.3, lon: -119.8 };
  } catch {
    return { lat: 39.3, lon: -119.8 };
  }
}

// queries thermal API endpoint for new data and stores GPS data as a flight path and thermal data in overlay
async function loadFlightPath() {
  const res     = await fetch(thermalURL(), { cache: "no-store" });
  const payload = await res.json();
  const points  = Array.isArray(payload) ? payload : (payload.wildfire_data || []);

  const coords = [];
  for (const pt of points) {
    coords.push([pt.latitude, pt.longitude]);
    lastTimestamp = Math.max(lastTimestamp, pt.time_stamp);
    appendPoint(pt.latitude, pt.longitude, [pt.high_temp, pt.low_temp]);
  }

  if (coords.length) {
    pathLine = L.polyline(coords, { color: "red" }).addTo(map);
    map.fitBounds(pathLine.getBounds());
  }
  overlay.render({ fitBounds: false });
}

function startDataPolling() {
  if (dataTimer) clearInterval(dataTimer);
  fetchNewPoints();
  dataTimer = setInterval(fetchNewPoints, DATA_INTERVAL);
}

async function fetchNewPoints() {
  const res     = await fetch(thermalURL(), { cache: "no-store" });
  const payload = await res.json();
  const points  = Array.isArray(payload) ? payload : (payload.wildfire_data || []);

  for (const pt of points) {
    if (pt.time_stamp > lastTimestamp) {
      lastTimestamp = pt.time_stamp;
      drawPoint(pt);
    }
  }
}

// Draw flight path and call thermalOverlay render
function drawPoint(pt) {
  if (!pathLine) {
    pathLine = L.polyline([[pt.latitude, pt.longitude]], { color: "red" }).addTo(map);
  } else {
    pathLine.addLatLng([pt.latitude, pt.longitude]);
  }
  appendPoint(pt.latitude, pt.longitude, [pt.high_temp, pt.low_temp]);
  overlay.render({ fitBounds: false });
  map.panTo([pt.latitude, pt.longitude]);
}