import { displayWeather } from "./weather_script.js";
import ThermalOverlay from "./thermal.js";
import TimelineController from "./timeline.js";

const fireName = new URLSearchParams(window.location.search).get("name");
let map, overlay, timeline;
let statusData = [];
let baseLayers;

document.addEventListener("DOMContentLoaded", async () => {
  setFireTitle();
  setDefaultDateTime();

  await initializeMap();
  await initializeOverlay();
  await initializeTimeline();
  await initializeCharts();

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
  map = L.map('map').setView([center.lat, center.lon], 14);

  // base layer
  const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors'
  });
  const satLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: 'Tiles © Esri' }
  );

  osmLayer.addTo(map);
  baseLayers = { osm: osmLayer, satellite: satLayer };

  L.marker([center.lat, center.lon])
    .addTo(map)
    .bindTooltip(fireName || 'Unknown Fire')
    .openTooltip();

  displayWeather(center.lat, center.lon);

  // Map / Sat Buttons
  document.getElementById('btnMapView').addEventListener('click', () => {
    if (map.hasLayer(baseLayers.satellite)) map.removeLayer(baseLayers.satellite);
    if (!map.hasLayer(baseLayers.osm))       map.addLayer(baseLayers.osm);
    document.getElementById('btnMapView').classList.add('active');
    document.getElementById('btnSatelliteView').classList.remove('active');
  });

  document.getElementById('btnSatelliteView').addEventListener('click', () => {
    if (map.hasLayer(baseLayers.osm))       map.removeLayer(baseLayers.osm);
    if (!map.hasLayer(baseLayers.satellite)) map.addLayer(baseLayers.satellite);
    document.getElementById('btnSatelliteView').classList.add('active');
    document.getElementById('btnMapView').classList.remove('active');
  });
}

async function initializeOverlay() {
  overlay = new ThermalOverlay(map, { mode: "fire" });
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

async function initializeCharts() {
  const resp = await fetch(`/api/fire_status?name=${encodeURIComponent(fireName)}`);
  if (!resp.ok) throw new Error("Failed to fetch fire status");
  statusData = await resp.json();

  statusData.forEach(d => d.ts = new Date(d.time_stamp));

  renderAllCharts("all");
}

function renderAllCharts(scope) {
  const now = new Date();
  let start, end = now;

  switch (scope) {
    case "6-hours":
      start = new Date(now.getTime() - 6 * 3600 * 1000);
      break;
    case "1-day":
      start = new Date(now.getTime() - 24 * 3600 * 1000);
      break;
    case "3-days":
      start = new Date(now.getTime() - 3 * 24 * 3600 * 1000);
      break;
    case "1-week":
      start = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
      break;
    case "all":
    default:
      const extent = d3.extent(statusData, d => d.ts);
      start = extent[0];
      end   = extent[1];
      break;
  }

  const xDomain = [start, end];

  renderLineChart("#size-chart",      statusData, "size",      "Fire Size", xDomain);
  renderLineChart("#flights-chart",   statusData, "flights",   "Flights",   xDomain);
  renderLineChart("#intensity-chart", statusData, "intensity", "Intensity", xDomain);
}

function renderLineChart(containerSelector, data, valueKey, yLabel, xDomain) {
  const margin = { top: 20, right: 30, bottom: 30, left: 50 };
  const width  = document.querySelector(containerSelector).clientWidth  - margin.left - margin.right;
  const height = document.querySelector(containerSelector).clientHeight - margin.top  - margin.bottom;

  d3.select(containerSelector).selectAll("svg").remove();

  const svg = d3.select(containerSelector)
    .append("svg")
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
    .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleTime()
    .domain(xDomain || d3.extent(data, d => d.ts))
    .range([0, width]);

  const y = d3.scaleLinear()
    .domain(d3.extent(data, d => d[valueKey])).nice()
    .range([height, 0]);

  svg.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x).ticks(5));

  svg.append("g")
    .call(d3.axisLeft(y).ticks(4));

  svg.append("text")
    .attr("x", width/2)
    .attr("y", height + margin.bottom - 5)
    .attr("text-anchor", "middle")
    .text("Time");

  svg.append("text")
    .attr("transform", "rotate(-90)")
    .attr("x", -height/2)
    .attr("y", -margin.left + 15)
    .attr("text-anchor", "middle")
    .text(yLabel);

  const line = d3.line()
    .x(d => x(d.ts))
    .y(d => y(d[valueKey]));

  svg.append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke-width", 2)
    .attr("stroke", "#ff4500")
    .attr("d", line);
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

  document.querySelectorAll(".timeline-scope-selector button")
    .forEach(btn => {
      btn.addEventListener("click", () => {
        document
          .querySelector(".timeline-scope-selector .active")
          .classList.remove("active");
        btn.classList.add("active");

        const scope = btn.getAttribute("data-scope");
        renderAllCharts(scope);
      });
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