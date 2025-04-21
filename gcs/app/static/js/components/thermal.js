class ThermalOverlay {
  constructor(mapInstance, { mode = "fire" } = {}) {
    this.map = mapInstance;
    this.mode = mode;
    this.heatLayer = null;
    this.thermalData = [];
    this.avgAltitude = null;
    this.colorGradient = {
      0.0: "rgba(0,0,255, 0)",  
      0.4: "rgba(0,0,255, 0.2)",
      0.6: "rgba(0,255,0, 0.4)", 
      0.8: "rgba(255,255,0,0.7)",
      1.0: "rgba(255,  0,  0,1.0)"
    };

    this.minZoom = 5;
    this.maxZoom = 18;
    this.map.setMinZoom(this.minZoom);
    this.map.setMaxZoom(this.maxZoom);

    // Fire mode
    this.fireCutoff = 0.20;
    this.fireMinOpacity = 0.35;
    // Flight mode
    this.flightCutoff = 0.0;
    this.flightMinOpacity = 0.5;

    this.map.on("zoomend", () => {
      if (this.heatLayer) {
        this.render();
      }
    });
  }

  async loadThermalData(name, time_stamp = null, flight_id = null) {
    try {
      let url = `/api/thermal/${encodeURIComponent(name)}`;
      if (time_stamp || flight_id) {
        const params = new URLSearchParams();
        if (time_stamp) params.append("time_stamp", time_stamp);
        if (flight_id)  params.append("flight_id", flight_id);
        url += "?" + params.toString();
      }
  
      const response = await fetch(url);
      const data     = await response.json();
      if (!Array.isArray(data) || data.length === 0) {
        console.warn("No thermal data returned");
        this.thermalData = [];
        this.avgAltitude = null;
        return [];
      }
  
      const rawPoints = data.map(point => ({
        lat:       point.latitude,
        lng:       point.longitude,
        high_temp: point.high_temp,
        low_temp:  point.low_temp,
        altitude:  point.altitude,
        timestamp: point.time_stamp
      }));
  
      let pointsToProcess;
      if (this.mode === "flight") {
        // in flight mode: keep every point, no deduplication
        pointsToProcess = rawPoints;
      } else {
        // in fire mode: bucket‑based deduplication
        const THRESHOLD_METERS   = 150;
        const METERS_PER_DEG_LAT = 111_320;
        const bucketDegLat       = THRESHOLD_METERS / METERS_PER_DEG_LAT;
        const buckets = new Map();
  
        rawPoints.forEach(pt => {
          const metersPerDegLng = METERS_PER_DEG_LAT * Math.cos(pt.lat * Math.PI/180);
          const bucketDegLng    = THRESHOLD_METERS / metersPerDegLng;
          const keyLat = Math.floor(pt.lat / bucketDegLat);
          const keyLng = Math.floor(pt.lng / bucketDegLng);
          const key    = `${keyLat}:${keyLng}`;
  
          const existing = buckets.get(key);
          if (!existing || pt.timestamp > existing.timestamp) {
            buckets.set(key, pt);
          }
        });
  
        pointsToProcess = Array.from(buckets.values());
      }
  
      const avgTemps = pointsToProcess.map(p => (p.high_temp + p.low_temp) / 2);
      const minTemp  = Math.min(...avgTemps);
      const maxTemp  = Math.max(...avgTemps);
  
      const finalPoints = pointsToProcess.map(p => {
        const avgTemp   = (p.high_temp + p.low_temp) / 2;
        const intensity = (maxTemp > minTemp)
          ? (avgTemp - minTemp) / (maxTemp - minTemp)
          : 1;
        return {
          lat:       p.lat,
          lng:       p.lng,
          intensity,
          altitude:  p.altitude,
          timestamp: p.timestamp
        };
      });
  
      this.thermalData = finalPoints;
      this.avgAltitude = finalPoints.reduce((sum, pt) => sum + pt.altitude, 0) 
                       / finalPoints.length;
  
      console.log("Using", pointsToProcess.length, "points;", 
                  "avgAltitude =", this.avgAltitude);
      return this.thermalData;
  
    } catch (error) {
      console.error("Error loading thermal data:", error);
      return [];
    }
  }  

  calculateDynamicRadius() {
    if (!this.avgAltitude) return 25;
    
    const currentZoom = this.map.getZoom();
    const fov = 55;
    
    const groundRadiusMeters = this.avgAltitude * Math.tan((fov / 2) * Math.PI / 180);
    const centerLat = this.map.getCenter().lat;
    const metersPerPixel = 156543.03392 * Math.cos(centerLat * Math.PI / 180) / Math.pow(2, currentZoom);

    let pixelRadius = groundRadiusMeters / metersPerPixel;
    pixelRadius = Math.max(pixelRadius, 1);
    pixelRadius = Math.min(pixelRadius, 50);
    
    return pixelRadius;
  }

  render(options = {}) {
    if (this.heatLayer) {
      this.map.removeLayer(this.heatLayer);
    }

    const isFlight = this.mode === "flight";
    const cutoff = isFlight ? this.flightCutoff : this.fireCutoff;

    const heatData = this.thermalData
      .filter(p => p.intensity > cutoff)
      .map(p => [p.lat, p.lng, p.intensity]);

    const radius = this.calculateDynamicRadius();

    let blur;
    const currentZoom = this.map.getZoom();
    const span = this.maxZoom - this.minZoom;
    const zoomFrac = (currentZoom - this.minZoom) / span;
    const maxBlur = radius * 1.5;
    blur = Math.max(0, maxBlur * (1 - zoomFrac));

    const minOpacity = isFlight ? this.flightMinOpacity : this.fireMinOpacity;

    const useLocalExtrema = isFlight ? true : false;
    const max = isFlight ? 1 : undefined;

    // Heatmap options
    const heatOptions = {
      radius:       radius,
      blur:         blur,
      max:          max,
      useLocalExtrema: useLocalExtrema,
      scaleRadius:  false,
      gradient:     this.colorGradient,
      minOpacity:   minOpacity
    };

    const flightOptions = {
      radius:       radius,
      blur:         0,
      useLocalExtrema: false,
      scaleRadius:  false,
      gradient:     this.colorGradient,
      minOpacity:   minOpacity,
      max: 1
    };

    if (isFlight) {
      // Render layer
      this.heatLayer = L.heatLayer(heatData, flightOptions).addTo(this.map);
    } else {
      this.heatLayer = L.heatLayer(heatData, heatOptions).addTo(this.map);
    }

    if (options.fitBounds && heatData.length) {
      const pts = heatData.map(d => [d[0], d[1]]);
      this.map.fitBounds(L.latLngBounds(pts));
    }

    return this.heatLayer;
  }

  async animateOverTime(fireId, startTime, endTime, stepSeconds, onStep) {
    const steps = Math.ceil((endTime - startTime) / (stepSeconds * 1000));

    for (let i = 0; i < steps; i++) {
      const currentTime = new Date(startTime.getTime() + (i * stepSeconds * 1000));
      await this.loadThermalData(fireId, currentTime.toISOString());
      this.render();

      if (onStep) {
        onStep(currentTime, i, steps);
      }

      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }

  setColorMode(mode) {
    switch (mode) {
      case "standard":
        this.colorGradient = {
          0.0: "rgba(0, 0, 255, 0)",
          0.4: "blue",
          0.6: "lime",
          0.7: "yellow",
          0.8: "orange",
          1.0: "red"
        };
        break;
      case "intensity":
        this.colorGradient = {
          0.0: "transparent",
          0.2: "purple",
          0.4: "blue",
          0.6: "green",
          0.8: "yellow",
          1.0: "red"
        };
        break;
      case "accessibility":
        this.colorGradient = {
          0.0: "#313695",
          0.2: "#4575b4",
          0.4: "#74add1",
          0.6: "#abd9e9",
          0.8: "#fdae61",
          1.0: "#d73027"
        };
        break;
    }

    if (this.heatLayer) {
      this.heatLayer.setOptions({ gradient: this.colorGradient });
    }
  }
}

export default ThermalOverlay;