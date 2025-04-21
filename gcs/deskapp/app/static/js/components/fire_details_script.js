import { displayWeather } from "./weather_script.js";
import ThermalOverlay from "./thermal.js";
import TimelineController from "./timeline.js";

const fireName = new URLSearchParams(window.location.search).get("name");
let map, overlay, timeline;

document.addEventListener("DOMContentLoaded", async () => {
  setFireTitle();
  setDefaultDateTime();

  await initializeMap();
  await initializeOverlay();
  await initializeTimeline();

  bindUIEvents();
});

function setFireTitle() {
  const title = document.getElementById("fire-title");
  if (title) {
    title.textContent = fireName || "Unknown Fire";
  }
}

function setDefaultDateTime() {
  const now = new Date();
  const dateInput = document.getElementById("date-select");
  const timeInput = document.getElementById("time-select");

  if (dateInput && timeInput) {
    dateInput.value = now.toISOString().split("T")[0];
    timeInput.value = now.toTimeString().split(":").slice(0, 2).join(":");
  }
}

async function fetchFireCenter() {
  try {
    const response = await fetch(`/wildfire_markers?filter=active`);
    if (!response.ok) throw new Error("Failed to fetch wildfire markers");

    const wildfires = await response.json();
    const fire = wildfires.find(f => f.name === fireName);
    return fire
      ? { lat: fire.avg_latitude, lon: fire.avg_longitude }
      : { lat: 39.3, lon: -119.8 };
  } catch (error) {
    console.error("Error fetching fire center:", error);
    return { lat: 39.3, lon: -119.8 };
  }
}

async function initializeMap() {
  const center = await fetchFireCenter();

  map = L.map("map").setView([center.lat, center.lon], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  L.marker([center.lat, center.lon])
    .addTo(map)
    .bindTooltip(fireName || "Unknown Fire")
    .openTooltip();

  displayWeather(center.lat, center.lon);
}

async function initializeOverlay() {
  overlay = new ThermalOverlay(map);
  await overlay.loadThermalData(fireName);
  overlay.render({ fitBounds: true });
}

async function initializeTimeline() {
  const container = document.getElementById("timeline-container");
  if (!container) {
    console.warn("Missing timeline container element");
    return;
  }

  timeline = new TimelineController("timeline-container", { allowScrubbing: true, showTime: true });
  await timeline.loadData(fireName);

  timeline.onTimeChange(async (timestamp) => {
    console.log("Time changed!", timestamp); 
    if (timestamp && overlay) {
      await overlay.loadThermalData(fireName, timestamp.toISOString());
      overlay.render();
    }
  });
  
}

async function loadHeatmapAtTime(timestamp) {
  if (!overlay) return;

  await overlay.loadThermalData(fireName, timestamp.toISOString());
  overlay.render();
}

async function updateHeatmapFromInputs() {
  const date = document.getElementById("date-select")?.value;
  const time = document.getElementById("time-select")?.value;

  if (!date || !time) return;

  const timestamp = new Date(`${date}T${time}`);
  await loadHeatmapAtTime(timestamp);
}

function selectGradient(event) {
  if (!overlay) return;

  const selectedGradient = JSON.parse(event.target.getAttribute("data-gradient"));
  overlay.colorGradient = selectedGradient;
  document.querySelector(".color-bar").style.background = event.target.style.background;
  overlay.render();
}

async function searchMap() {
  const input = document.getElementById("search-location");
  const location = input?.value;
  if (!location) return alert("Please enter a location");

  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(location)}`
    );
    const results = await response.json();
    if (results.length > 0) {
      const { lat, lon } = results[0];
      map.setView([lat, lon], 12);
    } else {
      alert("Location not found");
    }
  } catch (error) {
    console.error("Search error:", error);
    alert("Search failed");
  }
}

function bindUIEvents() {
  document.getElementById("date-select")?.addEventListener("change", updateHeatmapFromInputs);
  document.getElementById("time-select")?.addEventListener("change", updateHeatmapFromInputs);

  document.querySelectorAll(".gradient-option").forEach(option => {
    option.addEventListener("click", selectGradient);
  });

  document.getElementById("search-location")?.addEventListener("keydown", e => {
    if (e.key === "Enter") searchMap();
  });

  document.getElementById("refresh-weather")?.addEventListener("click", () => {
    const center = map?.getCenter();
    if (center) displayWeather(center.lat, center.lng);
  });
}