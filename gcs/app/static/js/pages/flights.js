// retrieves the list of all flights from the API endpoint
async function fetchFlights() {
    const res = await fetch('/api/flights');
    if (!res.ok) {
      throw new Error(`Failed to fetch flights: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  }
  
  // fetches detailed data for a given fire name and flight ID
  async function fetchFlightDetails(name, flightId) {
    const url = `/api/flights/${encodeURIComponent(name)}?flight_id=${flightId}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch flight details: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  }
  
  // calculate number of points, flight distance (km), and flight duration (mins)
  function computeMetrics(data) {
    if (!data.wildfire_data || data.wildfire_data.length < 2) return null;
  
    const haversine = (lat1, lon1, lat2, lon2) => {
      const R = 6371;
      const toRad = d => d * Math.PI / 180;
      const dlat = toRad(lat2 - lat1);
      const dlon = toRad(lon2 - lon1);
      const a = Math.sin(dlat/2)**2
              + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2))
              * Math.sin(dlon/2)**2;
      return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };
  
    let totalDist = 0;
    for (let i = 0; i < data.wildfire_data.length - 1; i++) {
      const a = data.wildfire_data[i];
      const b = data.wildfire_data[i + 1];
      totalDist += haversine(a.latitude, a.longitude, b.latitude, b.longitude);
    }
  
    const t1 = new Date(data.wildfire_data[0].time_stamp / 1e6);
    const t2 = new Date(data.wildfire_data.at(-1).time_stamp / 1e6);
    const durationMin = (t2 - t1) / 60000;
  
    return {
      points: data.wildfire_data.length,
      distance: totalDist.toFixed(2),
      duration: durationMin.toFixed(1)
    };
  }
  
  // create the clickable card element summarizing flight and computed metrics
  function createFlightCard(flight, metrics) {
    const card = document.createElement('div');
    card.className = 'card mb-3 card-hover';
    card.style.cursor = 'pointer';
  
    const body = document.createElement('div');
    body.className = 'card-body';
  
    const title = document.createElement('h5');
    title.className = 'card-title';
    title.textContent = `Flight ${flight.flight_id} – ${flight.name}`;
  
    const subtitle = document.createElement('h6');
    subtitle.className = 'card-subtitle text-muted mb-2';

    const secs = Number(flight.time_started);
    const ms = secs * 1000;
    subtitle.textContent = new Date(ms).toLocaleDateString();  // show date only
  
    const stats = document.createElement('p');
    stats.className = 'card-text small';
    stats.textContent = metrics
      ? `Data Points: ${metrics.points}, Distance: ${metrics.distance} km, Duration: ${metrics.duration} min`
      : 'No metrics available.';
  
    body.append(title, subtitle, stats);
    card.appendChild(body);
  
    card.addEventListener('click', () => {
      const url = `/flight_details?name=${encodeURIComponent(flight.name)}&flight_id=${flight.flight_id}`;
      window.location.href = url;
    });
  
    return card;
  }
  
  // main process
  // fetches all flights, groups by fire name, retrieves details for each, computes metrics, and appends flight cards.
  async function renderFlights() {
    const flights = await fetchFlights();
    const container = document.getElementById('flights-container');
    container.innerHTML = '';
  
    const grouped = flights.reduce((acc, f) => {
      (acc[f.name] = acc[f.name] || []).push(f);
      return acc;
    }, {});
  
    for (const [fireName, fireFlights] of Object.entries(grouped)) {
      const section = document.createElement('div');
      section.className = 'mb-4';
  
      const header = document.createElement('h4');
      header.textContent = fireName;
      section.appendChild(header);
  
      for (const flight of fireFlights) {
        const details = await fetchFlightDetails(flight.name, flight.flight_id);
        const metrics = computeMetrics(details);
        const card = createFlightCard(flight, metrics);
        section.appendChild(card);
      }
  
      container.appendChild(section);
    }
  }
  
  function setupSearch() {
    document
      .getElementById('search-fire')
      .addEventListener('input', ({ target }) => {
        const term = target.value.toLowerCase();
        document.querySelectorAll('#flights-container h4').forEach(header => {
          header.parentElement.style.display =
            header.textContent.toLowerCase().includes(term) ? '' : 'none';
        });
      });
  }
  
  document.addEventListener('DOMContentLoaded', async () => {
    await renderFlights();
    setupSearch();
  });  