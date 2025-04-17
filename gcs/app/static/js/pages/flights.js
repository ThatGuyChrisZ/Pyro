async function fetchFlights() {
    const res = await fetch('/api/flights');
    return await res.json();
}

async function fetchFlightDetails(flightId) {
    const res = await fetch(`/api/flights/${flightId}`);
    return await res.json();
}

function computeMetrics(data) {
    if (!data.wildfire_data || data.wildfire_data.length < 2) return null;

    const haversine = (lat1, lon1, lat2, lon2) => {
        const R = 6371;
        const toRad = deg => deg * Math.PI / 180;
        const dlat = toRad(lat2 - lat1);
        const dlon = toRad(lon2 - lon1);
        const a = Math.sin(dlat/2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlon/2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };

    let totalDist = 0;
    for (let i = 0; i < data.wildfire_data.length - 1; i++) {
        const a = data.wildfire_data[i];
        const b = data.wildfire_data[i + 1];
        totalDist += haversine(a.latitude, a.longitude, b.latitude, b.longitude);
    }

    const t1 = new Date(data.wildfire_data[0].time_stamp / 1_000_000);
    const t2 = new Date(data.wildfire_data.at(-1).time_stamp / 1_000_000);
    const durationMin = (t2 - t1) / 60000;

    return {
        points: data.wildfire_data.length,
        distance: totalDist.toFixed(2),
        duration: durationMin.toFixed(1)
    };
}

function createFlightCard(flight, metrics) {
    const card = document.createElement('div');
    card.className = 'card mb-3';

    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('h5');
    title.className = 'card-title';
    title.textContent = `Flight ${flight.flight_id} – ${flight.name}`;

    const subtitle = document.createElement('h6');
    subtitle.className = 'card-subtitle text-muted mb-2';
    subtitle.textContent = new Date(flight.time_started / 1000000).toLocaleString();

    const stats = document.createElement('p');
    stats.className = 'card-text small';
    stats.textContent = metrics
        ? `Data Points: ${metrics.points}, Distance: ${metrics.distance} km, Duration: ${metrics.duration} min`
        : 'No metrics available.';

    body.appendChild(title);
    body.appendChild(subtitle);
    body.appendChild(stats);
    card.appendChild(body);

    return card;
}

async function renderFlights() {
    const flights = await fetchFlights();
    const container = document.getElementById('flights-container');
    container.innerHTML = '';

    const grouped = flights.reduce((acc, flight) => {
        acc[flight.name] = acc[flight.name] || [];
        acc[flight.name].push(flight);
        return acc;
    }, {});

    for (const [fireName, fireFlights] of Object.entries(grouped)) {
        const section = document.createElement('div');
        section.className = 'mb-4';

        const header = document.createElement('h4');
        header.textContent = fireName;
        section.appendChild(header);

        for (const flight of fireFlights) {
        const details = await fetchFlightDetails(flight.flight_id);
        const metrics = computeMetrics(details);
        const card = createFlightCard(flight, metrics);
        section.appendChild(card);
        }

        container.appendChild(section);
    }
}

function setupSearch() {
    const input = document.getElementById('search-fire');
    input.addEventListener('input', () => {
        const term = input.value.toLowerCase();
        document.querySelectorAll('#flights-container h4').forEach(header => {
        const section = header.parentElement;
        section.style.display = header.textContent.toLowerCase().includes(term) ? '' : 'none';
        });
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await renderFlights();
    setupSearch();
});
