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
              .on("click", () => {
                this.selectedFire = fire;
                this.updateFireInfoPanel(fire);
              });
  
            this.markers.push(marker);
          }
        });
      } catch (error) {
        console.error("Error loading wildfire markers:", error);
      }
    }
  
    updateFireInfoPanel(fire) {
      const panel = document.getElementById('fireInfoPanel');
  
      panel.innerHTML = `
        <h5>${fire.name}</h5>
        <hr>
        <p><strong>Status:</strong> ${fire.status}</p>
        <p><strong>Location:</strong> ${fire.avg_latitude.toFixed(4)}, ${fire.avg_longitude.toFixed(4)}</p>
        <p><strong>Altitude:</strong> ${fire.alt ? fire.alt.toFixed(1) + ' m' : 'N/A'}</p>
        <p><strong>Temperature Range:</strong> ${fire.low_temp}°C - ${fire.high_temp}°C</p>
        <p><strong>Last Updated:</strong> ${fire.last_date_received} ${fire.last_time_received}</p>
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