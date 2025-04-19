// Moved from Database
async function getNearestCity(lat, lon) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch reverse geocode');
    const data = await response.json();
    const address = data.address || {};
    return address.city || address.town || address.village || address.county || address.state || "Unknown Location";
  } catch (error) {
    console.error("Error getting nearest city:", error);
    return "Unknown Location";
  }
}

class FiresPage {
  constructor() {
    this.map = null;
    this.markers = [];
    this.selectedFire = null;
    this.init();
  }

  async init() {
    this.initMap();
    await this.loadWildfireMarkers('active');
    window.addEventListener('resize', () => this.handleResize());
  }

  initMap() {
    this.map = L.map('fireMap').setView([39.8283, -98.5795], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(this.map);
  }

  async loadWildfireMarkers(filter = 'active') {
    try {
      const response = await fetch(`/wildfire_markers?filter=${filter}`);
      if (!response.ok) throw new Error('Failed to fetch wildfire markers');

      const fires = await response.json();
      this.markers.forEach(marker => this.map.removeLayer(marker));
      this.markers = [];

      const wildfireIcon = L.icon({
        iconUrl: 'static/assets/wildfire-icon.webp',
        iconSize: [40, 40],
        iconAnchor: [20, 40],
        popupAnchor: [0, -40],
      });

      fires.forEach(fire => {
        if (fire.avg_latitude && fire.avg_longitude) {
          const marker = L.marker([fire.avg_latitude, fire.avg_longitude], { icon: wildfireIcon })
            .addTo(this.map)
            .bindTooltip(fire.name, { permanent: false, direction: "top" })
            .on("click", async () => {
              this.selectedFire = fire;
              await this.updateFireInfoPanel(fire);
            });
          this.markers.push(marker);
        }
      });
    } catch (error) {
      console.error("Error loading wildfire markers:", error);
    }
  }

  async loadComparisonData(name) {
    try {
      const response = await fetch(`/fire_comparison?name=${encodeURIComponent(name)}`);
      if (!response.ok) throw new Error('Failed to fetch comparison data');
      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Error loading comparison data:", error);
      return null;
    }
  }

  async updateFireInfoPanel(fire) {
    const panel = document.getElementById('fireInfoPanel');
  
    panel.innerHTML = `
      <h5>${fire.name}</h5>
      <hr>
      <p>Loading previous day comparison...</p>
    `;
  
    const compData = await this.loadComparisonData(fire.name);
    if (compData) {
      fire.prev_size = compData.prev_size;
      fire.prev_intensity = compData.prev_intensity;
    }

    const nearestCity = await getNearestCity(fire.avg_latitude, fire.avg_longitude);
  
    function getChangeIndicator(current, previous) {
      if (previous == null || previous === 0) return '';
      const diff = current - previous;
      const percentChange = ((diff) / previous * 100).toFixed(1);
      if (diff > 0) {
        return `<span style="color: red;">▲ ${percentChange}%</span>`;
      } else if (diff < 0) {
        return `<span style="color: green;">▼ ${Math.abs(percentChange)}%</span>`;
      } else {
        return `<span style="color: gray;">— 0%</span>`;
      }
    }
  
    // Set Intensity Threshold
    function getIntensityColor(intensity) {
      if (intensity < 100) return "green";
      else if (intensity < 200) return "orange";
      else return "red";
    }
  
    let sizeBar = '';
    if (fire.prev_size != null && fire.prev_size > 0) {
      const maxSize = Math.max(fire.size, fire.prev_size);
      const currentSizePercent = (fire.size / maxSize) * 100;
      const prevSizePercent = (fire.prev_size / maxSize) * 100;
      sizeBar = `
        <div style="
          position: relative;
          width: 100px;
          height: 12px;
          background-color: #ddd;
          border-radius: 4px;
          overflow: hidden;
          display: inline-block;
          vertical-align: middle;
          margin-right: 8px;">
          <div style="
            position: absolute;
            left: 0;
            top: 0;
            width: ${prevSizePercent}%;
            height: 100%;
            background-color: lightgray;">
          </div>
          <div style="
            position: absolute;
            left: 0;
            top: 0;
            width: ${currentSizePercent}%;
            height: 100%;
            background-color: blue;
            opacity: 0.7;">
          </div>
        </div>
      `;
    } else {
      sizeBar = `
        <div style="
          width: 100px;
          height: 12px;
          background-color: #ddd;
          border-radius: 4px;
          display: inline-block;
          vertical-align: middle;
          margin-right: 8px;">
        </div>
      `;
    }
  
    let intensityBar = '';
    if (fire.prev_intensity != null) {
      const currentIntensityPercent = fire.intensity * 100;
      const prevIntensityPercent = fire.prev_intensity * 100;
      intensityBar = `
        <div style="
          position: relative;
          width: 100px;
          height: 12px;
          background-color: #ddd;
          border-radius: 4px;
          overflow: hidden;
          display: inline-block;
          vertical-align: middle;
          margin-right: 8px;">
          <div style="
            position: absolute;
            left: 0;
            top: 0;
            width: ${prevIntensityPercent}%;
            height: 100%;
            background-color: lightgray;">
          </div>
          <div style="
            position: absolute;
            left: 0;
            top: 0;
            width: ${currentIntensityPercent}%;
            height: 100%;
            background-color: ${getIntensityColor(fire.intensity)};">
          </div>
        </div>
      `;
    } else {
      intensityBar = `
        <div style="
          width: 100px;
          height: 12px;
          background-color: #ddd;
          border-radius: 4px;
          display: inline-block;
          vertical-align: middle;
          margin-right: 8px;">
        </div>
      `;
    }
  
    const sizeIndicator = fire.prev_size ? getChangeIndicator(fire.size, fire.prev_size) : '';
    const intensityIndicator = fire.prev_intensity ? getChangeIndicator(fire.intensity, fire.prev_intensity) : '';
  
    panel.innerHTML = `
      <h5>${fire.name}</h5>
      <hr>
      <p><strong>Status:</strong> ${fire.status}</p>
      <p><strong>Location:</strong> ${nearestCity}</p>
      <p>
        <strong>Size:</strong> ${fire.size.toFixed(2)} sq km 
        ${sizeIndicator ? `<small>(vs. ${fire.prev_size.toFixed(2)} sq km ${sizeIndicator})</small>` : ''}
        <br>
        ${sizeBar}
      </p>
      <p>
        <strong>Intensity:</strong> ${intensityBar} 
        ${intensityIndicator ? `<small>(${intensityIndicator})</small>` : ''}
      </p>
      <p><strong>Last Updated:</strong> ${new Date(fire.time_stamp / 1000000).toLocaleString()}</p>

      <div class="text-center mt-3">
        <a href="/fire_details?name=${encodeURIComponent(fire.name)}" class="btn btn-sm btn-primary">View Details</a>
      </div>
    `;
  }  

  handleResize() {
    if (this.map) {
      this.map.invalidateSize();
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.firesPage = new FiresPage();
});