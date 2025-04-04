class TimelineController {
    constructor(containerId, options = {}) {
      this.container = document.getElementById(containerId);
      this.options = Object.assign({
        height: 80,
        padding: 20,
        markerRadius: 6,
        lineColor: '#cccccc',
        activeColor: '#ff4500',
        flightColors: {},
        showFlights: true,
        showTime: true,
        allowScrubbing: true
      }, options);
      
      this.width = this.container.clientWidth - (this.options.padding * 2);
      this.startTime = null;
      this.endTime = null;
      this.currentTime = null;
      this.flights = [];
      this.thermalReadings = [];
      this.selectedFlight = null;
      
      this.callbacks = {
        onTimeChange: null,
        onFlightSelect: null
      };
      
      this.init();
    }
    
    init() {
      this.svg = d3.select(this.container)
        .append('svg')
        .attr('width', '100%')
        .attr('height', this.options.height);
        
      this.baseGroup = this.svg.append('g')
        .attr('transform', `translate(${this.options.padding}, ${this.options.padding})`);
        
      this.axisGroup = this.baseGroup.append('g')
        .attr('class', 'timeline-axis');
        
      this.linesGroup = this.baseGroup.append('g')
        .attr('class', 'timeline-lines');
        
      this.flightGroup = this.baseGroup.append('g')
        .attr('class', 'timeline-flights');
        
      this.markersGroup = this.baseGroup.append('g')
        .attr('class', 'timeline-markers');
        
      this.currentTimeGroup = this.baseGroup.append('g')
        .attr('class', 'timeline-current-time');
        
      if (this.options.allowScrubbing) {
        this.baseGroup.append('rect')
          .attr('class', 'timeline-overlay')
          .attr('width', this.width)
          .attr('height', this.options.height - (this.options.padding * 2))
          .attr('fill', 'transparent')
          .on('mousedown', (event) => this.startScrubbing(event))
          .on('mousemove', (event) => this.scrub(event))
          .on('mouseup', () => this.stopScrubbing())
          .on('mouseleave', () => this.stopScrubbing());
      }
      
      this.addPlayControls();
      
      this.isScrubbing = false;
    }
    
    async loadData(name) {
        try {
          const thermalResponse = await fetch(`/api/thermal/${name}`);
          const thermalRaw = await thermalResponse.json();
      
          if (!thermalRaw.length) {
            console.warn("No thermal data returned for:", name);
            return;
          }
      
          // Filter out invalid timestamps
          const validThermalData = thermalRaw.filter(d => typeof d.time_stamp === "number" && d.time_stamp > 0);
      
          if (!validThermalData.length) {
            console.warn("All thermal data had invalid timestamps.");
            return;
          }
      
          const timestamps = validThermalData.map(d => new Date(d.time_stamp / 1_000_000));
          this.startTime = new Date(Math.min(...timestamps.map(d => d.getTime())));
          this.endTime = new Date(Math.max(...timestamps.map(d => d.getTime())));
          this.currentTime = this.startTime;
      
          const temps = validThermalData.flatMap(d => [d.high_temp, d.low_temp]);
          const minTemp = Math.min(...temps);
          const maxTemp = Math.max(...temps);
      
          this.thermalReadings = validThermalData
            .map(row => {
              const timestamp = new Date(row.time_stamp / 1_000_000);
              if (isNaN(timestamp.getTime())) return null; 
              const avgTemp = (row.high_temp + row.low_temp) / 2;
              return {
                timestamp,
                intensity: (avgTemp - minTemp) / (maxTemp - minTemp)
              };
            })
            .filter(Boolean); 
      
          this.render();
      
          return {
            startTime: this.startTime,
            endTime: this.endTime,
            thermalReadings: this.thermalReadings
          };
        } catch (error) {
          console.error("Error loading timeline data:", error);
        }
      }
      
      
      
    
    render() {
      if (!this.startTime || !this.endTime) return;
      
      this.axisGroup.selectAll('*').remove();
      this.linesGroup.selectAll('*').remove();
      this.flightGroup.selectAll('*').remove();
      this.markersGroup.selectAll('*').remove();
      this.currentTimeGroup.selectAll('*').remove();
      
      this.timeScale = d3.scaleTime()
        .domain([this.startTime, this.endTime])
        .range([0, this.width]);
        
      const axis = d3.axisBottom(this.timeScale)
        .ticks(d3.timeHour.every(1))
        .tickFormat(d3.timeFormat('%H:%M'));
        
      this.axisGroup
        .attr('transform', `translate(0, ${this.options.height - (this.options.padding * 3)})`)
        .call(axis);
        
      this.linesGroup.append('line')
        .attr('x1', 0)
        .attr('y1', this.options.height / 2 - this.options.padding)
        .attr('x2', this.width)
        .attr('y2', this.options.height / 2 - this.options.padding)
        .attr('stroke', this.options.lineColor)
        .attr('stroke-width', 2);
        
      // Draw thermal intensity graph
      if (this.thermalReadings.length > 0) {
        const intensityScale = d3.scaleLinear()
          .domain([0, d3.max(this.thermalReadings, d => d.intensity)])
          .range([this.options.height / 2 - this.options.padding, 0]);
          
        const line = d3.line()
          .x(d => this.timeScale(new Date(d.timestamp)))
          .y(d => intensityScale(d.intensity))
          .curve(d3.curveMonotoneX);
          
        this.linesGroup.append('path')
          .datum(this.thermalReadings)
          .attr('fill', 'none')
          .attr('stroke', 'rgba(255, 69, 0, 0.7)')
          .attr('stroke-width', 2)
          .attr('d', line);
      }
      
      // Draw flight bars
      if (this.options.showFlights && this.flights.length > 0) {
        this.flightGroup.selectAll('.flight-bar')
          .data(this.flights)
          .enter()
          .append('rect')
          .attr('class', 'flight-bar')
          .attr('x', d => this.timeScale(new Date(d.startTime)))
          .attr('y', this.options.height / 2 - this.options.padding / 2 - 4)
          .attr('width', d => {
            const start = this.timeScale(new Date(d.startTime));
            const end = this.timeScale(new Date(d.endTime));
            return Math.max(end - start, 4); // Minimum width of 4px
          })
          .attr('height', 8)
          .attr('fill', d => this.options.flightColors[d.id] || '#666')
          .attr('stroke', '#333')
          .attr('stroke-width', 1)
          .attr('rx', 2)
          .attr('ry', 2)
          .attr('opacity', d => d.id === this.selectedFlight ? 1 : 0.7)
          .on('click', (event, d) => {
            this.selectFlight(d.id);
            if (this.callbacks.onFlightSelect) {
              this.callbacks.onFlightSelect(d.id);
            }
          })
          .append('title')
          .text(d => `Flight ${d.id}: ${this.formatTime(new Date(d.startTime))} - ${this.formatTime(new Date(d.endTime))}`);
      }
      
      this.drawCurrentTimeMarker();
    }
    
    drawCurrentTimeMarker() {
      this.currentTimeGroup.selectAll('*').remove();
      
      if (!this.currentTime || typeof this.timeScale !== 'function') return;
      
      const x = this.timeScale(this.currentTime);
      
      this.currentTimeGroup.append('line')
        .attr('x1', x)
        .attr('y1', 0)
        .attr('x2', x)
        .attr('y2', this.options.height - (this.options.padding * 3))
        .attr('stroke', this.options.activeColor)
        .attr('stroke-width', 2);
        
      this.currentTimeGroup.append('circle')
        .attr('cx', x)
        .attr('cy', this.options.height / 2 - this.options.padding)
        .attr('r', this.options.markerRadius)
        .attr('fill', this.options.activeColor)
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
        
      // Show current time
      if (this.options.showTime) {
        this.currentTimeGroup.append('text')
          .attr('x', x)
          .attr('y', -5)
          .attr('text-anchor', 'middle')
          .attr('font-size', '12px')
          .attr('font-weight', 'bold')
          .text(this.formatTime(this.currentTime));
      }
    }
    
    setCurrentTime(timestamp) {
      this.currentTime = new Date(timestamp);
      this.drawCurrentTimeMarker();
      
      if (this.callbacks.onTimeChange) {
        this.callbacks.onTimeChange(this.currentTime);
      }
    }
    
    selectFlight(flightId) {
      this.selectedFlight = flightId;
      this.render();
    }
    
    startScrubbing(event) {
      this.isScrubbing = true;
      this.scrub(event);
    }
    
    scrub(event) {
        if (!this.isScrubbing || !this.timeScale) return;
      
        const rect = this.container.getBoundingClientRect();
        const x = event.clientX - rect.left - this.options.padding;
        let time = this.timeScale.invert(x);
      
        if (time < this.startTime) time = this.startTime;
        if (time > this.endTime) time = this.endTime;
      
        this.setCurrentTime(time);
    }
      
    
    stopScrubbing() {
      this.isScrubbing = false;
    }
    
    addPlayControls() {
      const controlsDiv = document.createElement('div');
      controlsDiv.className = 'timeline-controls';
      controlsDiv.style.marginTop = '10px';
      controlsDiv.style.display = 'flex';
      controlsDiv.style.alignItems = 'center';
      controlsDiv.style.justifyContent = 'center';

    const playBtn = document.createElement('button');
    playBtn.className = 'btn btn-primary btn-sm';
    playBtn.innerHTML = '<i class="fas fa-play"></i>';
    playBtn.title = 'Play animation';
    
    const pauseBtn = document.createElement('button');
    pauseBtn.className = 'btn btn-secondary btn-sm';
    pauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
    pauseBtn.title = 'Pause animation';
    pauseBtn.style.marginLeft = '5px';
    
    const speedSelect = document.createElement('select');
    speedSelect.className = 'form-select form-select-sm';
    speedSelect.style.width = '100px';
    speedSelect.style.marginLeft = '10px';
    
    const speeds = [
      { label: '0.5x', value: 0.5 },
      { label: '1x', value: 1 },
      { label: '2x', value: 2 },
      { label: '5x', value: 5 },
      { label: '10x', value: 10 }
    ];
    
    speeds.forEach(speed => {
      const option = document.createElement('option');
      option.value = speed.value;
      option.textContent = speed.label;
      speedSelect.appendChild(option);
    });
    
    speedSelect.value = 1; 
    
    const timeDisplay = document.createElement('div');
    timeDisplay.className = 'time-display';
    timeDisplay.style.marginLeft = '15px';
    timeDisplay.style.fontFamily = 'monospace';
    timeDisplay.style.fontSize = '14px';
    
    controlsDiv.appendChild(playBtn);
    controlsDiv.appendChild(pauseBtn);
    controlsDiv.appendChild(speedSelect);
    controlsDiv.appendChild(timeDisplay);
    
    this.container.appendChild(controlsDiv);
    
    this.isPlaying = false;
    this.animationSpeed = 1;
    this.lastFrameTime = null;
    this.animationRequestId = null;
    
    const updateTimeDisplay = () => {
      if (!this.currentTime) return;
      
      const formattedTime = this.formatTime(this.currentTime);
      timeDisplay.textContent = formattedTime;
    };
    
    const animationStep = (timestamp) => {
      if (!this.isPlaying) return;
      
      if (!this.lastFrameTime) {
        this.lastFrameTime = timestamp;
      }
      
      const elapsed = timestamp - this.lastFrameTime;
      
      if (elapsed > 50) {
        this.lastFrameTime = timestamp;
        
        const newTime = new Date(this.currentTime.getTime() + (elapsed * this.animationSpeed * 10));
        
        if (newTime > this.endTime) {
          this.setCurrentTime(this.endTime);
          this.stopPlayback();
        } else {
          this.setCurrentTime(newTime);
        }
        
        updateTimeDisplay();
      }
      
      this.animationRequestId = requestAnimationFrame(animationStep);
    };
    
    playBtn.addEventListener('click', () => {
      if (this.isPlaying) return;
      
      if (this.currentTime >= this.endTime) {
        this.setCurrentTime(this.startTime);
      }
      
      this.isPlaying = true;
      this.lastFrameTime = null;
      this.animationRequestId = requestAnimationFrame(animationStep);
      
      updateTimeDisplay();
    });
    
    pauseBtn.addEventListener('click', () => {
      this.stopPlayback();
    });
    
    speedSelect.addEventListener('change', () => {
      this.animationSpeed = parseFloat(speedSelect.value);
    });
    
    updateTimeDisplay();
  }
  
  stopPlayback() {
    this.isPlaying = false;
    if (this.animationRequestId) {
      cancelAnimationFrame(this.animationRequestId);
      this.animationRequestId = null;
    }
  }
  
  formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  }
  
  onTimeChange(callback) {
    this.callbacks.onTimeChange = callback;
  }
  
  onFlightSelect(callback) {
    this.callbacks.onFlightSelect = callback;
  }
  
  setFlightColors(colors) {
    this.options.flightColors = colors;
    this.render();
  }
  
  getVisibleTimeframe() {
    return {
      start: this.startTime,
      end: this.endTime,
      current: this.currentTime
    };
  }
  
  resize() {
    this.width = this.container.clientWidth - (this.options.padding * 2);
    this.svg.attr('width', '100%');
    
    if (this.timeScale) {
      this.timeScale.range([0, this.width]);
      this.render();
    }
  }
}

export default TimelineController;