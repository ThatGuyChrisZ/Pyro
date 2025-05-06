// returns a wrapped version of function that can only execute once per wait interval
// used to slow down thermalOverlay updates
function throttle(fn, wait) {
  let last = 0;
  let timeout = null;
  return function(...args) {
    const now = Date.now();
    const remaining = wait - (now - last);
    if (remaining <= 0) {
      clearTimeout(timeout);
      timeout = null;
      last = now;
      fn.apply(this, args);
    } else if (!timeout) {
      timeout = setTimeout(() => {
        last = Date.now();
        timeout = null;
        fn.apply(this, args);
      }, remaining);
    }
  };
}

export default class ThermalOverlay {
  // initializes map instance based on mode (flight or fire)
  constructor(mapInstance, {
    mode              = "fire",
    recentWindowHours = 24,
    minHighTemp       = 200
  } = {}) {
    this.map            = mapInstance;
    this.mode           = mode;
    this.heatLayer      = null;
    this.rawCache       = null;
    this.thermalData    = [];
    this.avgAltitude    = null;

    this.recentWindowMs = recentWindowHours * 3600 * 1000;
    this.minHighTemp    = minHighTemp;

    this.colorGradient = {
      0.0: "rgba(0,0,255,0)",
      0.4: "rgba(0,0,255,0.2)",
      0.6: "rgba(0,255,0,0.4)",
      0.8: "rgba(255,255,0,0.7)",
      1.0: "rgba(255,0,0,1)"
    };

    this.minZoom = 5;
    this.maxZoom = 18;
    this.map.setMinZoom(this.minZoom);
    this.map.setMaxZoom(this.maxZoom);

    this.fireCutoff      = 0.20;
    this.fireMinOpacity  = 0.35;
    this.flightCutoff    = 0.0;
    this.flightMinOpacity= 0.5;

    // render only occurs every 200ms
    this.render = throttle(this._render.bind(this), 200);
    this.map.on("zoomend", () => {
      if (this.heatLayer) this.render();
    });
  }

  // retrieves all thermal points for a fire (and optional flight) from thermal API endpoint
  async _fetchAll(name, flight_id = null) {
    let url = `/api/thermal/${encodeURIComponent(name)}`;
    if (flight_id) url += `?flight_id=${encodeURIComponent(flight_id)}`;
    const response = await fetch(url);
    const data = await response.json();
    this.rawCache = (Array.isArray(data) ? data : [])
      .filter(pt => pt.high_temp >= this.minHighTemp);
  }

  // ensures raw data is fetched once, then processes it in a Web Worker
  async loadThermalData(name, time_stamp = null, flight_id = null) {
    if (!this.rawCache) {
      await this._fetchAll(name, flight_id);
    }
    return this._processInWorker(time_stamp);
  }

  // filter, deduplicate, and compute intensity for each point in worker
  _processInWorker(time_stamp) {
    return new Promise((resolve, reject) => {
      const workerCode = `
        onmessage = function(e) {
          const { raw, mode, windowMs, ts } = e.data;
          // 1) filter out future points for both modes
          let pts = raw;
          if (ts != null) {
            pts = pts.filter(p => Number(p.time_stamp) <= ts);
          }
          // 2) in fire mode, also enforce recent window
          if (mode === 'fire' && ts != null) {
            pts = pts.filter(p => {
              const t = Number(p.time_stamp);
              return t >= (ts - windowMs) && t <= ts;
            });
          }
          // 3) dedupe in fire mode
          let deduped;
          if (mode === 'flight') {
            deduped = pts;
          } else {
            const METERS_PER_DEG_LAT = 111320;
            const THRESHOLD_METERS = 150;
            const bucketLat = THRESHOLD_METERS / METERS_PER_DEG_LAT;
            const buckets = {};
            pts.forEach(p => {
              const keyLat = Math.floor(p.latitude / bucketLat);
              const mPerDegLng = METERS_PER_DEG_LAT * Math.cos(p.latitude * Math.PI/180);
              const bucketLng = THRESHOLD_METERS / mPerDegLng;
              const keyLng = Math.floor(p.longitude / bucketLng);
              const key = keyLat + ':' + keyLng;
              if (!buckets[key] || Number(p.time_stamp) > Number(buckets[key].time_stamp)) {
                buckets[key] = p;
              }
            });
            deduped = Object.values(buckets);
          }
          // 4) compute intensity
          const temps = deduped.map(p => (p.high_temp + p.low_temp)/2);
          const mn = Math.min(...temps);
          const mx = Math.max(...temps);
          const out = deduped.map(p => {
            const avg = (p.high_temp + p.low_temp)/2;
            return {
              lat: p.latitude,
              lng: p.longitude,
              intensity: mx>mn ? (avg - mn)/(mx - mn) : 1,
              altitude: p.altitude
            };
          });
          postMessage({ points: out });
        };
      `;
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      const worker = new Worker(URL.createObjectURL(blob));
      const ts = time_stamp
        ? (typeof time_stamp === 'string'
            ? new Date(time_stamp).getTime() * 1e6
            : Number(time_stamp))
        : null;
      worker.onmessage = ({ data }) => {
        this.thermalData = data.points;
        this.avgAltitude = data.points.reduce((s,p)=>s + p.altitude,0) / (data.points.length||1);
        this.render();
        resolve(this.thermalData);
        worker.terminate();
      };
      worker.onerror = e => reject(e);
      worker.postMessage({ raw: this.rawCache, mode: this.mode, windowMs: this.recentWindowMs * 1e6, ts });
    });
  }

  // removes existing heatLayer and draws a new heatmap layer
  _render(options = {}) {
    if (this.heatLayer) this.map.removeLayer(this.heatLayer);
    const isFlight = this.mode === 'flight';
    const cutoff = isFlight ? this.flightCutoff : this.fireCutoff;
    const heatData = this.thermalData
      .filter(p => p.intensity > cutoff)
      .map(p => [p.lat, p.lng, p.intensity]);
    const radius = this._calcRadius();
    const opts = isFlight ? this._flightOpts(radius) : this._fireOpts(radius);
    this.heatLayer = L.heatLayer(heatData, opts).addTo(this.map);
    if (options.fitBounds && heatData.length) {
      this.map.fitBounds(L.latLngBounds(heatData.map(d => [d[0], d[1]])));
    }
    return this.heatLayer;
  }

  // calculates heatmap point radius based on average altitude and current zoom
  _calcRadius() {
    if (!this.avgAltitude) return 25;
    const zoom = this.map.getZoom();
    const fov = 55;
    const groundRadius = this.avgAltitude * Math.tan((fov/2) * Math.PI/180);
    const lat0 = this.map.getCenter().lat;
    const mpp = 156543.03392 * Math.cos(lat0 * Math.PI/180) / Math.pow(2, zoom);
    let px = groundRadius / mpp;
    return Math.max(1, Math.min(px, 50));
  }

  // Fire Mode
  _fireOpts(radius) {
    return {
      radius,
      blur: radius * 1.5 * (1 - ((this.map.getZoom()-this.minZoom)/(this.maxZoom-this.minZoom))),
      max: undefined,
      useLocalExtrema: false,
      scaleRadius: false,
      gradient: this.colorGradient,
      minOpacity: this.fireMinOpacity
    };
  }

  // Flight Mode
  _flightOpts(radius) {
    return {
      radius,
      blur: 0,
      max: 1,
      useLocalExtrema: true,
      scaleRadius: false,
      gradient: this.colorGradient,
      minOpacity: this.flightMinOpacity
    };
  }
}