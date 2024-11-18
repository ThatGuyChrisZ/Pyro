// Fire icon
const wildfireIcon = L.icon({
    iconUrl: 'wildfire-icon.webp',
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
            console.log("Adding marker for:", wildfire.name, wildfire.latitude, wildfire.longitude);
            L.marker([wildfire.latitude, wildfire.longitude], { icon: wildfireIcon })
                .addTo(window.map)
                .bindTooltip(wildfire.name, { permanent: false, direction: "top" })
                .on("click", () => {
                    window.location.href = `fire_details.html?name=${encodeURIComponent(wildfire.name)}`;
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

async function loadWildfireLocations(filter) {
    const response = await fetch(`/wildfire_list?filter=${filter}`);
    const wildfireData = await response.json();

    wildfireData.forEach(wildfire => {
        const marker = L.marker([wildfire.latitude, wildfire.longitude])
            .addTo(map)
            .bindPopup(`<b>${wildfire.name}</b><br>Click for details.`);

        marker.on("click", () => {
            window.location.href = `fire_details.html?name=${encodeURIComponent(wildfire.name)}`;
        });
    });
}

async function loadTestData() {
    const response = await fetch('/heatmap_data');
    const heatmapData = await response.json();

    console.log("Loaded Heatmap Data:", heatmapData);

    if (window.heatmapLayer) {
        map.removeLayer(window.heatmapLayer);
    }
    window.heatmapLayer = L.heatLayer(heatmapData, {
        radius: 25,
        blur: 15,
        maxZoom: 18,
        gradient: {
            350: 'blue',
            400: 'lime',
            425: 'yellow',
            450: 'orange',
            500: 'red'
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

    let params = new URLSearchParams({ wildfire_id: wildfireName, date: date, time: time });
    let response = await fetch(`/heatmap_data?${params.toString()}`);
    let heatmapData = await response.json();

    if (window.heatmapLayer) {
        map.removeLayer(window.heatmapLayer);
    }

    window.heatmapLayer = L.heatLayer(heatmapData, {
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

async function searchByLocation() {
    let location = document.getElementById("search-location").value;
    let response = await fetch(`/search_location?query=${encodeURIComponent(location)}`);
    let locationData = await response.json();

    if (locationData) {
        map.setView([locationData.lat, locationData.lon], 12);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const menuItems = document.querySelectorAll('.menu-item a');
    menuItems.forEach(item => {
        if (window.location.href.includes(item.getAttribute('href'))) {
            item.style.color = '#ff9800';
        }
    });
});
document.addEventListener("DOMContentLoaded", loadMap);