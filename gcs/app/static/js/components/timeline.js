class TimelineController {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = Object.assign({
      height: 80,
      padding: 20,
      markerRadius: 6,
      lineColor: '#cccccc',
      activeColor: '#ff4500',
      showTime: true,
      allowScrubbing: true,
      defaultScope: '1-day'
    }, options);
    
    this.width = this.container.clientWidth - (this.options.padding * 2);
    this.startTime = null;
    this.endTime = null;
    this.currentTime = null;
    this.thermalReadings = [];
    this.brushEnabled = false;
    
    this.callbacks = {
      onTimeChange: null
    };
    
    this.scopeOptions = {
      '6-hours': 6 * 60 * 60 * 1000,
      '1-day': 24 * 60 * 60 * 1000,
      '3-days': 3 * 24 * 60 * 60 * 1000,
      '1-week': 7 * 24 * 60 * 60 * 1000,
      'all': null
    };
    
    this.currentScope = this.options.defaultScope;
    this.isPlaying = false;
    
    this.init();
  }
  
  init() {
    this.createControlUI();
    this.bindScopeButtons();
    
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
    
    document.addEventListener('keydown', (event) => this.handleKeyNavigation(event));
  }
  
  createControlUI() {
    const controlsRow = document.createElement('div');
    controlsRow.className = 'timeline-controls-row';
    controlsRow.style.display = 'flex';
    controlsRow.style.justifyContent = 'space-between';
    controlsRow.style.alignItems = 'center';
    controlsRow.style.marginBottom = '10px';
    
    this.dateDisplay = document.createElement('div');
    this.dateDisplay.className = 'timeline-date-display';
    this.dateDisplay.style.fontWeight = 'bold';
    this.dateDisplay.style.fontSize = '16px';
    
    controlsRow.appendChild(this.dateDisplay);
    
    this.container.appendChild(controlsRow);
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
      this.originalStartTime = new Date(Math.min(...timestamps.map(d => d.getTime())));
      this.originalEndTime = new Date();
      
      this.scopeOptions.all = this.originalEndTime - this.originalStartTime;
      
      this.currentTime = this.originalEndTime;
  
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
            intensity: (avgTemp - minTemp) / (maxTemp - minTemp),
            highTemp: row.high_temp,
            lowTemp: row.low_temp
          };
        })
        .filter(Boolean);
      
      // Update the timeline based on the selected scope
      this.updateTimelineScope();
  
      return {
        startTime: this.startTime,
        endTime: this.endTime,
        thermalReadings: this.thermalReadings
      };
    } catch (error) {
      console.error("Error loading timeline data:", error);
    }
  }
  
  updateTimelineScope() {
    const scopeDuration = this.scopeOptions[this.currentScope];
    
    if (scopeDuration === null) {
      this.startTime = new Date(this.originalStartTime);
      this.endTime = new Date(this.originalEndTime);
    } else {
      this.endTime = new Date(this.originalEndTime);
      this.startTime = new Date(this.endTime - scopeDuration);
      
      const buffer = scopeDuration * 0.05;
      this.startTime = new Date(this.startTime.getTime() - buffer);
    }
    
    if (this.currentTime < this.startTime) {
      this.currentTime = new Date(this.startTime);
    } else if (this.currentTime > this.endTime) {
      this.currentTime = new Date(this.endTime);
    }
    
    this.render();
    this.updateDateDisplay();
  }
  
  render() {
    if (!this.startTime || !this.endTime) return;
    
    this.axisGroup.selectAll('*').remove();
    this.linesGroup.selectAll('*').remove();
    this.markersGroup.selectAll('*').remove();
    this.currentTimeGroup.selectAll('*').remove();
    
    this.timeScale = d3.scaleTime()
      .domain([this.startTime, this.endTime])
      .range([0, this.width]);
    
    let tickFormatter;
    let tickInterval;
    
    switch (this.currentScope) {
      case '6-hours':
        tickFormatter = d3.timeFormat('%H:%M');
        tickInterval = d3.timeMinute.every(30);
        break;
      case '1-day':
        tickFormatter = d3.timeFormat('%H:%M');
        tickInterval = d3.timeHour.every(2);
        break;
      case '3-days':
        tickFormatter = d3.timeFormat('%b %d %H:%M');
        tickInterval = d3.timeHour.every(6);
        break;
      case '1-week':
        tickFormatter = d3.timeFormat('%b %d');
        tickInterval = d3.timeDay.every(1);
        break;
      case 'all':
        const duration = this.endTime - this.startTime;
        const days = duration / (24 * 60 * 60 * 1000);
        
        if (days <= 7) {
          tickFormatter = d3.timeFormat('%b %d');
          tickInterval = d3.timeDay.every(1);
        } else if (days <= 30) {
          tickFormatter = d3.timeFormat('%b %d');
          tickInterval = d3.timeDay.every(3);
        } else {
          tickFormatter = d3.timeFormat('%b %Y');
          tickInterval = d3.timeMonth.every(1);
        }
        break;
    }
    
    const axis = d3.axisBottom(this.timeScale)
      .ticks(tickInterval)
      .tickFormat(tickFormatter);
      
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
      const visibleReadings = this.thermalReadings.filter(
        d => d.timestamp >= this.startTime && d.timestamp <= this.endTime
      );
      
      if (visibleReadings.length > 0) {
        const intensityScale = d3.scaleLinear()
          .domain([0, 1])
          .range([this.options.height / 2 - this.options.padding, 0]);
          
        const line = d3.line()
          .x(d => this.timeScale(d.timestamp))
          .y(d => intensityScale(d.intensity))
          .curve(d3.curveMonotoneX);
          
        this.linesGroup.append('path')
          .datum(visibleReadings)
          .attr('fill', 'none')
          .attr('stroke', 'rgba(255, 69, 0, 0.7)')
          .attr('stroke-width', 2)
          .attr('d', line);
      }
    }
    
    this.drawCurrentTimeMarker();
    if (this.brushEnabled) this.drawBrush();
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
    
    this.updateDateDisplay();
  }
  
  updateDateDisplay() {
    if (!this.currentTime) return;
    
    const formattedDate = this.currentTime.toLocaleDateString(undefined, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
    
    this.dateDisplay.textContent = formattedDate;
  }
  
  handleKeyNavigation(event) {
    if (!this.timeScale || !this.currentTime) return;
    
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();

    if (event.key === ' ') {
      event.preventDefault();
      if (this.isPlaying) {
        this.pauseBtn.click();
      } else {
        this.playBtn.click();
      }
      return;
    }
    
    // Calculate time step based on current scope
    let timeStep;
    switch (this.currentScope) {
      case '6-hours':
        timeStep = 10 * 60 * 1000;
        break;
      case '1-day':
        timeStep = 30 * 60 * 1000; 
        break;
      case '3-days':
        timeStep = 2 * 60 * 60 * 1000;
        break;
      case '1-week':
        timeStep = 6 * 60 * 60 * 1000; 
        break;
      case 'all':
        const duration = this.endTime - this.startTime;
        timeStep = duration / 48;
        break;
      default:
        timeStep = 30 * 60 * 1000;
    }
    
    const direction = event.key === 'ArrowLeft' ? -1 : 1;
    const newTime = new Date(this.currentTime.getTime() + (direction * timeStep));
    
    if (newTime < this.startTime) {
      this.setCurrentTime(this.startTime);
    } else if (newTime > this.endTime) {
      this.setCurrentTime(this.endTime);
    } else {
      this.setCurrentTime(newTime);
    }
  }

  drawBrush() {
    const brush = d3.brushX()
      .extent([[0,0],[this.width,this.options.height]])
      .on('end', ({selection}) => {
        if (!selection) return;
  
        const [x0,x1] = selection;
        this.startTime   = this.timeScale.invert(x0);
        this.endTime     = this.timeScale.invert(x1);
        this.currentTime = this.endTime;
  
        this.svg.selectAll('.brush').remove();
  
        this.brushEnabled = false;
   
        if (this.zoomBtn) {
          this.zoomBtn.classList.remove('active');
        }
  
        this.render();
      });
  
    // remove any old brush
    this.svg.selectAll('.brush').remove();
  
    // draw it fresh
    this.svg.append('g')
      .attr('class','brush')
      .attr('transform',`translate(${this.options.padding},${this.options.padding})`)
      .call(brush);
  }
  
  setCurrentTime(timestamp) {
    this.currentTime = new Date(timestamp);
    this.drawCurrentTimeMarker();
    
    if (this.callbacks.onTimeChange) {
      this.callbacks.onTimeChange(this.currentTime);
    }
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
    playBtn.style.marginLeft = '5px';
    
    const pauseBtn = document.createElement('button');
    pauseBtn.className = 'btn btn-secondary btn-sm';
    pauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
    pauseBtn.title = 'Pause animation';
    pauseBtn.style.marginLeft = '5px';

    const zoomBtn = document.createElement('button');
    zoomBtn.className = 'btn btn-outline-secondary btn-sm ms-2';
    zoomBtn.innerHTML = '<i class="fas fa-search-plus"></i>';
    zoomBtn.title = 'Toggle scope';
    zoomBtn.addEventListener('click', () => {
      this.brushEnabled = !this.brushEnabled;
      zoomBtn.classList.toggle('active', this.brushEnabled);
      if (!this.brushEnabled) {
        this.svg.selectAll('.brush').remove();
      } else {
        this.drawBrush();
      }
    });    
    controlsDiv.appendChild(zoomBtn);
    this.zoomBtn = zoomBtn;

    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn btn-outline-secondary btn-sm ms-2';
    exportBtn.innerHTML = '<i class="fas fa-download"></i>';
    exportBtn.title = 'Export CSV';
    exportBtn.addEventListener('click', () => {
      const { start, end } = this.getVisibleTimeframe();
      window.open(`/download_csv?start=${+start}&end=${+end}`, '_blank');
    });
    exportBtn.style.marginLeft = '5px';
    pauseBtn.style.marginRight = '5px';
    exportBtn.style.marginRight = '5px';
    controlsDiv.appendChild(exportBtn);
    
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
  
  getVisibleTimeframe() {
    return {
      start: this.startTime,
      end: this.endTime,
      current: this.currentTime
    };
  }

  bindScopeButtons() {
    const buttons = document.querySelectorAll('.timeline-scope-selector .btn-group button');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        this.currentScope = btn.getAttribute('data-scope');
        
        this.updateTimelineScope();
      });
    });
  }
  
  
  resize() {
    this.width = this.container.clientWidth - (this.options.padding * 2);
    this.svg.attr('width', '100%');
    
    if (this.timeScale) {
      this.timeScale.range([0, this.width]);
      this.render();
    }
  }
  
  // filter thermal readings by current time
  getThermalReadingsAtCurrentTime() {
    if (!this.currentTime || !this.thermalReadings.length) {
      return [];
    }
    
    const sortedReadings = [...this.thermalReadings].sort((a, b) => {
      return Math.abs(a.timestamp - this.currentTime) - Math.abs(b.timestamp - this.currentTime);
    });
    
    return sortedReadings[0];
  }
}

export default TimelineController;