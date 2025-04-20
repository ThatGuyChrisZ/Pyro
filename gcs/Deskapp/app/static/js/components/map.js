// Fire icon
const wildfireIcon = L.icon({
    iconUrl: 'app/static/assets/wildfire-icon.webp',
    iconSize: [40, 40],
    iconAnchor: [20, 40],
    popupAnchor: [0, -40],
});

L.marker([wildfire.latitude, wildfire.longitude], { icon: wildfireIcon })
    .addTo(window.map)
    .bindTooltip(wildfire.name, { permanent: false, direction: "top" })
    .on("click", () => {
        window.location.href = `fire_details.html?name=${encodeURIComponent(wildfire.name)}`;
    });

async function loadWildfireMarkers(filter = "active") {
    try {
        const response = await fetch(`/wildfire_markers?filter=${filter}`);
        if (!response.ok) throw new Error("Failed to fetch wildfire markers");
        const wildfireData = await response.json();

        if (wildfireData.length === 0) {
            console.warn("No wildfires found for filter:", filter);
            return;
        }

        wildfireData.forEach((wildfire) => {
            console.log("Adding marker for:", wildfire.name, wildfire.avg_latitude, wildfire.avg_longitude);

            const marker = L.marker([wildfire.avg_latitude, wildfire.avg_longitude], { icon: wildfireIcon })
                .addTo(window.map)
                .bindTooltip(wildfire.name, { permanent: false, direction: "top" })
                .on("click", () => {
                    window.location.href = `fire_details.html?name=${encodeURIComponent(wildfire.name)}`;
                });

            marker.on("mouseover", function () {
                marker.bindPopup(`
                    <strong>${wildfire.name}</strong><br>
                    ${wildfire.first_date_received && wildfire.first_time_received
                        ? `<strong>Start Time:</strong> ${wildfire.first_date_received} ${wildfire.first_time_received}<br>` 
                        : ""
                    }
                    <strong>Last Updated:</strong> ${wildfire.last_updated} km²<br> 
                    <strong>Size:</strong> ${wildfire.size} km²
                `).openPopup();
            });

            marker.on("mouseout", function () {
                marker.closePopup();
            });
        });
    } catch (error) {
        console.error("Error loading wildfire markers:", error);
    }
}         

async function loadMap(filter = "active") {
    window.map = L.map("map").setView([39.305278, -119.8325], 8);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "© OpenStreetMap contributors"
    }).addTo(map);

    await loadWildfireMarkers(filter);
}

async function loadHeatmapData() {
    const response = await fetch('/heatmap_data');
    const heatmapData = await response.json();

    console.log("Loaded Heatmap Data:", heatmapData);

    if (window.heatmapLayer) {
        map.removeLayer(window.heatmapLayer);
    }

    const temperatures = heatmapData.flatMap(p => [p.high_temp, p.low_temp]);
    const minTemp = Math.min(...temperatures);
    const maxTemp = Math.max(...temperatures);

    const normalizedData = heatmapData.map(p => [
        p.latitude,
        p.longitude,
        (p.high_temp + p.low_temp) / 2 / (maxTemp - minTemp) // Normalized average temp
    ]);

    window.heatmapLayer = L.heatLayer(normalizedData, {
        radius: 25,
        blur: 15,
        maxZoom: 18,
        gradient: {
            0.1: 'blue',
            0.3: 'lime',
            0.5: 'yellow',
            0.7: 'orange',
            1.0: 'red'
        }
    }).addTo(map);
}

async function loadWildfireOptions() {
    let wildfireSelect = document.getElementById("wildfire-select");
    let response = await fetch("/wildfire_list");
    let wildfires = await response.json();

    wildfires.forEach(wildfire => {
        let option = document.createElement("option");
        option.value = wildfire.name;
        option.text = wildfire.name;
        wildfireSelect.appendChild(option);
    });
}

async function updateHeatmap() {
    let wildfireName = document.getElementById("wildfire-select").value;
    let date = document.getElementById("date-select").value;
    let time = document.getElementById("time-select").value;

    let params = new URLSearchParams({ name: wildfireName, date: date, time: time });
    let response = await fetch(`/heatmap_data?${params.toString()}`);
    let heatmapData = await response.json();

    if (window.heatmapLayer) {
        map.removeLayer(window.heatmapLayer);
    }

    const temperatures = heatmapData.flatMap(p => [p.high_temp, p.low_temp]);
    const minTemp = Math.min(...temperatures);
    const maxTemp = Math.max(...temperatures);

    const normalizedData = heatmapData.map(p => [
        p.latitude,
        p.longitude,
        (p.high_temp + p.low_temp) / 2 / (maxTemp - minTemp)
    ]);

    window.heatmapLayer = L.heatLayer(normalizedData, {
        radius: 25,
        blur: 15,
        maxZoom: 18,
        gradient: {
            0.1: 'blue',
            0.3: 'lime',
            0.5: 'yellow',
            0.7: 'orange',
            1.0: 'red'
        }
    }).addTo(map);
}

document.addEventListener("DOMContentLoaded", loadMap);