const fireName = new URLSearchParams(window.location.search).get("name");
let currentGradient = {
    0.6: "blue",
    0.7: "lime",
    0.8: "yellow",
    0.9: "orange",
    1: "red",
};

let map;
let heatLayer;

document.getElementById("fire-title").textContent = fireName || "Unknown Fire";

function setDefaultDateTime() {
    const now = new Date();
    document.getElementById("date-select").value = now.toISOString().split("T")[0];
    document.getElementById("time-select").value = now.toTimeString().split(":").slice(0, 2).join(":");
}

async function fetchFireCenter() {
    try {
        const response = await fetch(`/wildfire_markers?filter=active`);
        if (!response.ok) throw new Error("Failed to fetch wildfire markers");

        const wildfires = await response.json();
        const fire = wildfires.find(f => f.name === fireName);

        if (fire) {
            return { lat: fire.latitude, lon: fire.longitude };
        } else {
            console.warn("Fire not found in markers; defaulting map view.");
            return { lat: 39.3, lon: -119.8 };
        }
    } catch (error) {
        console.error(error);
        return { lat: 39.3, lon: -119.8 }; // Default coords
    }
}

async function initializeMap() {
    const center = await fetchFireCenter();

    map = L.map("map").setView([center.lat, center.lon], 16);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "© OpenStreetMap contributors",
    }).addTo(map);

    loadFireHeatmap();
}

async function loadFireHeatmap() {
    try {
        const date = document.getElementById("date-select").value;
        const time = document.getElementById("time-select").value;

        const queryParams = new URLSearchParams({ name: fireName });
        if (date) queryParams.append("date", date);
        if (time) queryParams.append("time", time);

        const response = await fetch(`/heatmap_data?${queryParams.toString()}`);
        if (!response.ok) throw new Error("Failed to fetch heatmap data");

        const heatmapData = await response.json();
        if (!heatmapData.length) {
            alert("No data available for the selected criteria.");
            return;
        }

        const temperatures = heatmapData.flatMap(p => [p.high_temp, p.low_temp]);
        const minTemp = Math.min(...temperatures);
        const maxTemp = Math.max(...temperatures);

        document.getElementById("low-temp").textContent = `${minTemp.toFixed(2)}°`;
        document.getElementById("high-temp").textContent = `${maxTemp.toFixed(2)}°`;

        const normalizedData = heatmapData.map(p => [
            p.latitude,
            p.longitude,
            (p.high_temp + p.low_temp) / 2 / (maxTemp - minTemp),
        ]);

        if (heatLayer) map.removeLayer(heatLayer);

        heatLayer = L.heatLayer(normalizedData, {
            radius: 50,
            blur: 35,
            gradient: currentGradient,
        }).addTo(map);
    } catch (error) {
        console.error(error);
        alert("An error occurred while loading the heatmap.");
    }
}

async function searchMap() {
    const location = document.getElementById("search-location").value;

    if (location) {
        try {
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(location)}`);
            const locationData = await response.json();

            if (locationData.length > 0) {
                const { lat, lon } = locationData[0];
                map.setView([lat, lon], 12);
            } else {
                alert("Location not found");
            }
        } catch (error) {
            console.error("Search failed:", error);
            alert("An error occurred while searching for the location.");
        }
    } else {
        alert("Please enter a location to search");
    }
}

function selectGradient(event) {
    const selectedGradient = JSON.parse(event.target.getAttribute("data-gradient"));
    currentGradient = selectedGradient;
    document.querySelector(".color-bar").style.background = event.target.style.background;
    loadFireHeatmap();
}

document.addEventListener("DOMContentLoaded", () => {
    setDefaultDateTime();

    document.querySelectorAll(".gradient-option").forEach(option => {
        option.addEventListener("click", selectGradient);
    });

    document.getElementById("search-location").addEventListener("keydown", (event) => {
        if (event.key === "Enter") searchMap();
    });

    initializeMap();
});