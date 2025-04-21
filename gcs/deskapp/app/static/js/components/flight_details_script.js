import TimelineController from "./timeline.js";
import ThermalOverlay from "./thermal.js";

const fireName = new URLSearchParams(window.location.search).get("name");
const flightId = new URLSearchParams(window.location.search).get("flight_id");

let map, timeline, overlay;
let pathLine = null;
let fullFlightData = [];

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

async function initializeMap() {
  const center = await fetchFireCenter();

  map = L.map("map").setView([center.lat, center.lon], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);
}

async function fetchFireCenter() {
  try {
    const response = await fetch(`/wildfire_markers?filter=active`);
    if (!response.ok) throw new Error("Failed to fetch wildfire markers");

    const wildfires = await response.json();
    const fire = wildfires.find(f => f.name === fireName);
    return fire ? { lat: fire.avg_latitude, lon: fire.avg_longitude } : { lat: 39.3, lon: -119.8 };
  } catch (error) {
    console.error("Error fetching fire center:", error);
    return { lat: 39.3, lon: -119.8 };
  }
}

async function initializeOverlay() {
  overlay = new ThermalOverlay(map);
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
  
    if (pathLine && map.hasLayer(pathLine)) {
      map.removeLayer(pathLine);
    }
  
    if (partialPoints.length > 0) {
      pathLine = L.polyline(partialPoints, { color: 'red' }).addTo(map);
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

    map.fitBounds(L.latLngBounds(fullFlightData.map(p => [p.lat, p.lng])));

    await overlay.loadThermalData(fireName, null, flightId);
    overlay.render();

  } catch (err) {
    console.error("Failed to load flight path:", err);
  }
}
  