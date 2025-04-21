import ThermalOverlay from "./thermal.js";

const fireName     = new URLSearchParams(window.location.search).get("name");
const flightId     = new URLSearchParams(window.location.search).get("flight_id");
const DATA_INTERVAL = 2000;  

let map, overlay, pathLine;
let lastTimestamp  = 0;
let dataTimer;
let knownFlightId = 0;

document.addEventListener("DOMContentLoaded", async () => {
  setTitle();

  // Waiting for new flight
  if (flightId == "null" || !flightId) {
    await fetchExistingFlights();
    pollForNewFlight();
    return; 
  }

  // Live flight mode
  await initializeMap();
  overlay = new ThermalOverlay(map, { mode: "flight" });
  await loadFlightPath();
  startDataPolling();
});


function setTitle() {
  const title = document.querySelector("h2");
  if (title) {
    if (flightId) {
      title.textContent = `${fireName} – Flight ${flightId} (LIVE)`;
    } else {
      title.textContent = `${fireName} – Awaiting new flight…`;
    }
  }
}

function flightsURL() {
  return `/api/flights/${encodeURIComponent(fireName)}`;
}

function thermalURL() {
  let url = `/api/thermal/${encodeURIComponent(fireName)}`;
  if (flightId) {
    url += `?flight_id=${encodeURIComponent(flightId)}`;
  }
  return url;
}

async function fetchExistingFlights() {
  const res = await fetch(flightsURL());
  const flights = await res.json();
  const ids = flights.map(f => f.flight_id ?? f.id);
  knownFlightId = ids.length ? Math.max(...ids) : 0;
}

function pollForNewFlight() {
  setInterval(async () => {
    const res = await fetch(flightsURL());
    const flights = await res.json();
    const ids = flights.map(f => f.flight_id ?? f.id);
    const maxId = ids.length ? Math.max(...ids) : 0;

    if (maxId > knownFlightId) {
      const url = new URL(window.location.href);
      url.searchParams.set("flight_id", maxId);
      window.location.replace(url);
    }
  }, DATA_INTERVAL);
}

function appendPoint(lat, lng, temps, altitude = null, timestamp = null) {
  const [high_temp, low_temp] = temps;
  const avgTemp = (high_temp + low_temp) / 2;
  overlay.thermalData = overlay.thermalData || [];
  overlay.thermalData.push({
    lat,
    lng,
    intensity: avgTemp,
    altitude,
    timestamp
  });
}

async function initializeMap() {
  const center = await fetchFireCenter();
  const container = document.getElementById("map");

  if (map != undefined) {
    map.off();
    map = map.remove();
    map = null;
  }

  //completely destroy map and identifiers left behind by leaflet
  container.innerHTML = '';
  container.className = '';
  delete container._leaflet_id;

  map = L.map("map").setView([center.lat, center.lon], 14);

  const osm = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 18, attribution: "© OpenStreetMap contributors" }
  ).addTo(map);

  const sat = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles © Esri" }
  );

  document.getElementById("btnMapView").addEventListener("click", () => {
    map.hasLayer(sat) && map.removeLayer(sat);
    !map.hasLayer(osm) && map.addLayer(osm);
    toggleActive("btnMapView","btnSatelliteView");
  });
  document.getElementById("btnSatelliteView").addEventListener("click", () => {
    map.hasLayer(osm) && map.removeLayer(osm);
    !map.hasLayer(sat) && map.addLayer(sat);
    toggleActive("btnSatelliteView","btnMapView");
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

async function fetchFireCenter() {
  try {
    const res = await fetch("/wildfire_markers?filter=active");
    if (!res.ok) throw new Error(res.statusText);
    const arr = await res.json();
    const f = arr.find(x => x.name === fireName);
    return f
      ? { lat: f.avg_latitude, lon: f.avg_longitude }
      : { lat: 39.3, lon: -119.8 };
  } catch {
    return { lat: 39.3, lon: -119.8 };
  }
}

async function loadFlightPath() {
  const res = await fetch( thermalURL(), { cache: "no-store" } );
  if (!res.ok) throw new Error(res.statusText);
  const payload = await res.json();

  const points = Array.isArray(payload)
    ? payload
    : (payload.wildfire_data || []);

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
  const res = await fetch( thermalURL(), { cache: "no-store" } );
  if (!res.ok) throw new Error(res.statusText);
  const payload = await res.json();
  const points = Array.isArray(payload)
    ? payload
    : (payload.wildfire_data || []);

  for (const pt of points) {
    if (pt.time_stamp > lastTimestamp) {
      lastTimestamp = pt.time_stamp;
      drawPoint(pt);
    }
  }
}

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