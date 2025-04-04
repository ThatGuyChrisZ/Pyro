class ThermalOverlay {
    constructor(mapInstance) {
      this.map = mapInstance;
      this.heatLayer = null;
      this.thermalData = [];
      this.colorGradient = {
        0.4: 'blue',
        0.6: 'lime',
        0.7: 'yellow',
        0.8: 'orange',
        1.0: 'red'
      };
    }
  
    async loadThermalData(name, time_stamp = null) {
        try {
          let url = `/api/thermal/${encodeURIComponent(name)}`;
          if (time_stamp) {
            url += `?time_stamp=${encodeURIComponent(time_stamp)}`;
          }
      
          const response = await fetch(url);
          const data = await response.json();
      
          if (!Array.isArray(data) || data.length === 0) {
            console.warn("No thermal data returned");
            this.thermalData = [];
            return [];
          }
      
          const temps = data.flatMap(p => [p.high_temp, p.low_temp]);
          const minTemp = Math.min(...temps);
          const maxTemp = Math.max(...temps);
      
          this.thermalData = data.map(point => {
            const avgTemp = (point.high_temp + point.low_temp) / 2;
            const intensity = (avgTemp - minTemp) / (maxTemp - minTemp);
            return [point.latitude, point.longitude, intensity];
          });
      
          return this.thermalData;
        } catch (error) {
          console.error('Error loading thermal data:', error);
          return [];
        }
    }
      
  
    render(options = {}) {
      // Remove existing heatmap if present
      if (this.heatLayer) {
        this.map.removeLayer(this.heatLayer);
      }
      
      const heatOptions = {
        radius: options.radius || 25,
        blur: options.blur || 15,
        maxZoom: options.maxZoom || 18,
        max: options.max || 1.0,
        gradient: this.colorGradient
      };
      
      this.heatLayer = L.heatLayer(this.thermalData, heatOptions);
      this.heatLayer.addTo(this.map);
      
      if (options.fitBounds && this.thermalData.length > 0) {
        const points = this.thermalData.map(point => [point[0], point[1]]);
        this.map.fitBounds(L.latLngBounds(points));
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
      switch(mode) {
        case 'standard':
          this.colorGradient = {
            0.4: 'blue',
            0.6: 'lime',
            0.7: 'yellow',
            0.8: 'orange',
            1.0: 'red'
          };
          break;
        case 'intensity':
          this.colorGradient = {
            0.0: 'transparent',
            0.2: 'purple',
            0.4: 'blue',
            0.6: 'green',
            0.8: 'yellow',
            1.0: 'red'
          };
          break;
        case 'accessibility':
          this.colorGradient = {
            0.0: '#313695',
            0.2: '#4575b4',
            0.4: '#74add1',
            0.6: '#abd9e9',
            0.8: '#fdae61',
            1.0: '#d73027'
          };
          break;
      }
      
      if (this.heatLayer) {
        this.heatLayer.setOptions({ gradient: this.colorGradient });
      }
    }
  }
  
  export default ThermalOverlay;