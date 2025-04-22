// flight_timeline.js

class FlightTimelineController {
    constructor(containerId, options = {}) {
      this.container = document.getElementById(containerId);
      this.options = Object.assign({
        height: 80,
        padding: 20,
        markerRadius: 6,
        lineColor: '#cccccc',
        activeColor: '#ff4500',
        showTime: true,
        allowScrubbing: true
      }, options);
  
      this.width = this.container.clientWidth - this.options.padding * 2;
      this.startTime = null;
      this.endTime = null;
      this.currentTime = null;
      this.thermalReadings = [];
      this.isScrubbing = false;
      this.isPlaying = false;
      this.callbacks = { onTimeChange: null };
  
      this._init();
    }
  
    _init() {
      this._createDateUI();

      this.svg = d3.select(this.container)
        .append('svg')
        .attr('width', '100%')
        .attr('height', this.options.height);
  
      this.baseGroup = this.svg.append('g')
        .attr('transform', `translate(${this.options.padding}, ${this.options.padding})`);
  
      this.axisGroup        = this.baseGroup.append('g').attr('class','timeline-axis');
      this.linesGroup       = this.baseGroup.append('g').attr('class','timeline-lines');
      this.currentTimeGroup = this.baseGroup.append('g').attr('class','timeline-current-time');
  
      if (this.options.allowScrubbing) {
        this.baseGroup.append('rect')
          .attr('class','timeline-overlay')
          .attr('width', this.width)
          .attr('height', this.options.height - this.options.padding*2)
          .attr('fill','transparent')
          .on('mousedown', e => this._startScrub(e))
          .on('mousemove', e => this._scrub(e))
          .on('mouseup',  () => this._stopScrub())
          .on('mouseleave', () => this._stopScrub());
      }
  
      document.addEventListener('keydown', e => this._onKey(e));
      this._createButtonUI();
    }
  
    _createDateUI() {
      const dateDiv = document.createElement('div');
      dateDiv.style.fontWeight = 'bold';
      dateDiv.style.fontSize   = '16px';
      dateDiv.style.margin     = '0 0 8px';
      this.dateDisplay = dateDiv;
      this.container.appendChild(dateDiv);
    }
  
    _createButtonUI() {
      const ctrls = document.createElement('div');
      ctrls.style.display = 'flex';
      ctrls.style.justifyContent = 'center';
      ctrls.style.alignItems = 'center';
      ctrls.style.margin = '8px 0';
  
      // play button
      const playBtn = document.createElement('button');
      playBtn.className = 'btn btn-primary btn-sm';
      playBtn.innerHTML = '<i class="fas fa-play"></i>';
      playBtn.title = 'Play animation';
      playBtn.addEventListener('click', () => this._play());
      ctrls.appendChild(playBtn);
  
      // pause button
      const pauseBtn = document.createElement('button');
      pauseBtn.className = 'btn btn-secondary btn-sm';
      pauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
      pauseBtn.title = 'Pause animation';
      pauseBtn.style.marginLeft = '5px';
      pauseBtn.addEventListener('click', () => this._pause());
      ctrls.appendChild(pauseBtn);
  
      this.container.appendChild(ctrls);
    }
  
    async loadData(fireName, flightId) {
      // fetch flight path for start/end
      const resp1 = await fetch(
        `/api/flights/${encodeURIComponent(fireName)}?flight_id=${flightId}`
      );
      const { wildfire_data = [] } = await resp1.json();
      const times = wildfire_data
        .map(pt => new Date(pt.time_stamp / 1_000_000))
        .filter(d => !isNaN(d));
  
      if (times.length) {
        this.startTime   = new Date(Math.min(...times));
        this.endTime     = new Date(Math.max(...times));
        this.currentTime = new Date(this.startTime);
      } else {
        const now = new Date();
        this.startTime = this.endTime = this.currentTime = new Date(now);
        console.warn('No flight-path timestamps returned for', flightId);
      }
  
      // fetch thermal data
      const resp2 = await fetch(
        `/api/thermal/${encodeURIComponent(fireName)}?flight_id=${flightId}`
      );
      const raw = await resp2.json();
      const valid = raw.filter(d => typeof d.time_stamp === 'number' && d.time_stamp > 0);
      const temps = valid.flatMap(d => [d.high_temp, d.low_temp]);
      const tmin = Math.min(...temps), tmax = Math.max(...temps);
  
      this.thermalReadings = valid.map(d => {
        const ts = new Date(d.time_stamp / 1_000_000);
        return {
          timestamp: ts,
          intensity: (((d.high_temp + d.low_temp) / 2 - tmin) / (tmax - tmin)),
          highTemp: d.high_temp,
          lowTemp: d.low_temp
        };
      }).filter(d => !isNaN(d.timestamp));

      this._render();
      return {
        startTime: this.startTime,
        endTime: this.endTime,
        thermalReadings: this.thermalReadings
      };
    }
  
    _render() {
      if (!this.startTime || !this.endTime) return;
  
      this.axisGroup.selectAll('*').remove();
      this.linesGroup.selectAll('*').remove();
      this.currentTimeGroup.selectAll('*').remove();
  
      this.width = this.container.clientWidth - this.options.padding * 2;
      this.timeScale = d3.scaleTime()
        .domain([this.startTime, this.endTime])
        .range([0, this.width]);
  
      const axis = d3.axisBottom(this.timeScale)
        .ticks(5)
        .tickFormat(d3.timeFormat('%H:%M:%S'));
      this.axisGroup
        .attr('transform', `translate(0, ${this.options.height - this.options.padding*3})`)
        .call(axis);
  
      this.linesGroup.append('line')
        .attr('x1', 0)
        .attr('y1', this.options.height/2 - this.options.padding)
        .attr('x2', this.width)
        .attr('y2', this.options.height/2 - this.options.padding)
        .attr('stroke', this.options.lineColor)
        .attr('stroke-width', 2);
  
      // thermal curve
      if (this.thermalReadings.length) {
        const vis = this.thermalReadings.filter(d =>
          d.timestamp >= this.startTime && d.timestamp <= this.endTime
        );
        if (vis.length) {
          const yScale = d3.scaleLinear()
            .domain([0,1])
            .range([this.options.height/2 - this.options.padding, 0]);
          const line = d3.line()
            .x(d => this.timeScale(d.timestamp))
            .y(d => yScale(d.intensity))
            .curve(d3.curveMonotoneX);
  
          this.linesGroup.append('path')
            .datum(vis)
            .attr('fill','none')
            .attr('stroke','rgba(255,69,0,0.7)')
            .attr('stroke-width',2)
            .attr('d', line);
        }
      }
  
      this._drawCurrentMarker();
    }
  
    _drawCurrentMarker() {
      this.currentTimeGroup.selectAll('*').remove();
  
      if (!this.currentTime || !this.timeScale) return;
      const x = this.timeScale(this.currentTime);
  
      this.currentTimeGroup.append('line')
        .attr('x1', x).attr('y1', 0)
        .attr('x2', x).attr('y2', this.options.height - this.options.padding*3)
        .attr('stroke', this.options.activeColor)
        .attr('stroke-width', 2);
  
      this.currentTimeGroup.append('circle')
        .attr('cx', x)
        .attr('cy', this.options.height/2 - this.options.padding)
        .attr('r', this.options.markerRadius)
        .attr('fill', this.options.activeColor)
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
  
      if (this.options.showTime) {
        this.currentTimeGroup.append('text')
          .attr('x', x).attr('y', -5)
          .attr('text-anchor','middle')
          .attr('font-size','12px')
          .attr('font-weight','bold')
          .text(this._formatTime(this.currentTime));
      }
  
      // update the date display above
      this.dateDisplay.textContent = this.currentTime.toLocaleString();
    }
  
    _formatTime(date) {
      return date.toLocaleTimeString([], {
        hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false
      });
    }
  
    _play() {
      if (this.isPlaying) return;
      if (this.currentTime >= this.endTime) this.currentTime = new Date(this.startTime);
      this.isPlaying = true;
      let last = null;
      const step = ts => {
        if (!this.isPlaying) return;
        if (!last) last = ts;
        const delta = ts - last;
        if (delta > 50) {
          last = ts;
          const next = new Date(this.currentTime.getTime() + delta * 10);
          this.currentTime = next > this.endTime ? this.endTime : next;
          this._drawCurrentMarker();
          this._emitTimeChange();
          if (this.currentTime >= this.endTime) this._pause();
        }
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
  
    _pause() {
      this.isPlaying = false;
    }
  
    _startScrub(e) {
      this.isScrubbing = true; this._scrub(e);
    }
    _scrub(e) {
      if (!this.isScrubbing || !this.timeScale) return;
      const rect = this.container.getBoundingClientRect();
      let x = e.clientX - rect.left - this.options.padding;
      x = Math.max(0, Math.min(x, this.width));
      this.currentTime = this.timeScale.invert(x);
      this._drawCurrentMarker();
      this._emitTimeChange();
    }
    _stopScrub() {
      this.isScrubbing = false;
    }
  
    _onKey(evt) {
      if (!this.timeScale || !this.currentTime) return;
      const step = (this.endTime - this.startTime) / 100;
      if (evt.key === 'ArrowLeft' || evt.key === 'ArrowRight') {
        evt.preventDefault();
        const dir = evt.key === 'ArrowLeft' ? -1 : 1;
        let nt = new Date(this.currentTime.getTime() + dir * step);
        nt = nt < this.startTime ? this.startTime : nt > this.endTime ? this.endTime : nt;
        this.currentTime = nt;
        this._drawCurrentMarker();
        this._emitTimeChange();
      }
    }
  
    _emitTimeChange() {
      if (this.callbacks.onTimeChange) {
        this.callbacks.onTimeChange(this.currentTime);
      }
    }
  
    onTimeChange(fn) {
      this.callbacks.onTimeChange = fn;
    }
  }
  
  export default FlightTimelineController;  