async function fetchData(endpoint) {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) throw new Error(`Failed to fetch data from ${endpoint}`);
        return await response.json();
    } catch (error) {
        console.error("Error fetching data:", error);
        return [];
    }
}

function renderTable(data, container) {
    if (data.length === 0) {
        container.innerHTML = "<p>No data available.</p>";
        return;
    }

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");

    const headers = Object.keys(data[0]);
    const headerRow = document.createElement("tr");
    headers.forEach((header) => {
        const th = document.createElement("th");
        th.textContent = header;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    data.forEach((row) => {
        const tr = document.createElement("tr");
        headers.forEach((header) => {
            const td = document.createElement("td");
            td.textContent = row[header];
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    container.innerHTML = "";
    container.appendChild(table);
}

async function loadWildfireStatus() {
    const data = await fetchData("/get_database");
    const container = document.getElementById("table-container");
    renderTable(data, container);

    const fireFilter = document.getElementById("fire-filter");
    fireFilter.innerHTML = '<option value="">Select a Fire</option>';
    data.forEach((fire) => {
        const option = document.createElement("option");
        option.value = fire.name;
        option.textContent = fire.name;
        fireFilter.appendChild(option);
    });
}

async function loadWildfireData(fireName) {
    const data = await fetchData(`/get_database?fire_name=${encodeURIComponent(fireName)}`);
    const container = document.getElementById("table-container");
    renderTable(data, container);
}

document.addEventListener("DOMContentLoaded", () => {
    const fireFilter = document.getElementById("fire-filter");

    fireFilter.addEventListener("change", () => {
        const selectedFire = fireFilter.value;
        if (selectedFire) {
            loadWildfireData(selectedFire);
        } else {
            loadWildfireStatus();
        }
    });

    loadWildfireStatus();
});