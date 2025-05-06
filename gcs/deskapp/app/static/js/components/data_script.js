// Defaults to display wildfires_status table filtered such that only the most recent record for each fire name is displayed

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
    headers.forEach(header => {
      const th = document.createElement("th");
      th.textContent = header;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
  
    data.forEach(row => {
      const tr = document.createElement("tr");
      headers.forEach(header => {
        const td = document.createElement("td");
  
        const value = row[header];
  
        if (typeof value === "number") {
          td.textContent = value.toFixed(2);
        } else {
          td.textContent = value;
        }
  
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  
    table.appendChild(thead);
    table.appendChild(tbody);
    container.innerHTML = "";
    container.appendChild(table);
  }
  
  
  async function loadWildfireStatusTable() {
    const container = document.getElementById("table-container");
    const data = await fetchData("/get_database?table=wildfire_status");
    renderTable(data, container);
  
    const wildfireData = await fetchData("/get_database?table=wildfires");
    const fireFilter = document.getElementById("fire-filter");
    fireFilter.innerHTML = '<option value="">Select a Fire</option>';
  
    const uniqueNames = [...new Set(wildfireData.map(row => row.name))];
    uniqueNames.forEach(name => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      fireFilter.appendChild(option);
    });
  }
  
  async function loadFilteredWildfireData(fireName) {
    const container = document.getElementById("table-container");
    const data = await fetchData(`/get_database?table=wildfires&fire_name=${encodeURIComponent(fireName)}`);
    renderTable(data, container);
  }
  
  document.addEventListener("DOMContentLoaded", () => {
    const fireFilter = document.getElementById("fire-filter");
  
    fireFilter.addEventListener("change", () => {
      const selectedFire = fireFilter.value;
      if (selectedFire) {
        loadFilteredWildfireData(selectedFire);
      } else {
        loadWildfireStatusTable(); // Reset to default
      }
    });
  
    loadWildfireStatusTable(); // Load default view
  });
  