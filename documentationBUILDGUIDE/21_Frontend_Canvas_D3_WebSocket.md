# 21 — Frontend: Canvas Animation, D3 Chart & WebSocket Logic (`overview.html` Part 2)

**File:** `fl_shap_dashboard/templates/pages/overview.html` (`{% block extra_scripts %}`)  
**Libraries:** D3.js v7 (CDN), Canvas API (native browser)  
**WebSocket URL:** `ws://localhost:8000/ws`

---

## Part 1: Canvas Cluster Bubble Animation

The `<canvas id="clusterCanvas">` renders an animated visualization of factory clustering.

### Data Initialization

```javascript
const RAW_CLUSTERS = {{ clusters_json|safe }};
// Injected from Django view: e.g.
// {"0": [{"factory_id":1,"name":"Factory Mumbai","dataset":"FD001"},
//         {"factory_id":3,...}],
//  "1": [{"factory_id":2,...}, {"factory_id":4,...}]}
// OR: {"unassigned": [...]} before clustering fires

const FACTORY_META = {
  1: {name:'Mumbai',  color:'#3B82F6', r:28, short:'F1'},
  2: {name:'Berlin',  color:'#6366F1', r:26, short:'F2'},
  3: {name:'Detroit', color:'#14B8A6', r:24, short:'F3'},
  4: {name:'Tokyo',   color:'#8B5CF6', r:28, short:'F4'},
};
// r = bubble radius (pixels)
// color = stroke and fill base color
```

### Clustering State Detection

```javascript
const assignedKeys = Object.keys(RAW_CLUSTERS).filter(k => k !== 'unassigned');
const isClustered  = assignedKeys.length > 0;
// isClustered = false → all factories at center (single FedAvg zone)
// isClustered = true  → factories spread to their cluster zones
```

### Bubble Construction

```javascript
let bubbles = [];
if (!isClustered) {
  // All 4 factories orbit a single central zone
  Object.values(FACTORY_META).forEach((m, i) => {
    bubbles.push({id: i+1, meta: m, cluster: 'center', x: W*0.5, y: H*0.5, r: m.r});
  });
} else {
  // Real cluster assignments from DB
  assignedKeys.forEach(cid => {
    RAW_CLUSTERS[cid].forEach(f => {
      const m = FACTORY_META[f.factory_id];
      bubbles.push({id: f.factory_id, meta: m, cluster: cid, x: W*0.5, y: H*0.5, r: m.r});
    });
  });
  // Any unassigned factories → center fallback
}
```

### Cluster Zone Centers

```javascript
function buildCenters() {
  const zones = {};
  if (!isClustered) {
    zones['center'] = {x: W*0.5, y: H*0.5, color: 'rgba(100,116,255,', label: 'FedAvg Training'};
  } else {
    const n = assignedKeys.length;
    assignedKeys.forEach((cid, i) => {
      const frac = (i + 1) / (n + 1);  // evenly spaced: 1/(n+1), 2/(n+1), ...
      zones[cid] = {
        x: W * frac,   // e.g. n=2: x = W*0.333, W*0.667
        y: H * 0.5,
        color: CLUSTER_PALETTE[i % CLUSTER_PALETTE.length],
        label: `Cluster ${cid}`
      };
    });
  }
  return zones;
}
```

### `drawFrame()` — Animation Loop

```javascript
function drawFrame() {
  ctx.clearRect(0, 0, W, H);

  // ── Zone backgrounds (dashed circles) ───────────────────────
  Object.entries(clusterZones).forEach(([key, c]) => {
    const r = isClustered ? 68 : 80;
    ctx.beginPath(); ctx.arc(c.x, c.y, r, 0, Math.PI*2);
    ctx.fillStyle   = c.color + '0.06)';      // 6% opacity fill
    ctx.strokeStyle = c.color + '0.25)';      // 25% opacity stroke
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([5, 4]);   // dashed circle outline
    ctx.fill(); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillText(c.label, c.x, c.y - r - 8); // label above zone
  });

  // ── Bubbles (orbiting elliptically within their zone) ────────
  bubbles.forEach(b => {
    const zone  = clusterZones[b.cluster] || clusterZones['center'];
    const phase = b.id * Math.PI / 2;      // unique phase per factory (90° apart)
    const orbitR = isClustered ? 20 : 30; // tighter orbit when clustered

    // Sinusoidal orbit: x = sin(t + phase) * R, y = cos(t + phase) * R * 0.7
    const jx = Math.sin(Date.now()/1400 + phase) * orbitR;
    const jy = Math.cos(Date.now()/1200 + phase) * (orbitR * 0.7);

    // Smooth lerp toward target (0.018 = ~1.8% per frame = gentle drift)
    b.x = lerp(b.x, zone.x + jx, 0.018);
    b.y = lerp(b.y, zone.y + jy, 0.018);

    // Draw glow shadow
    ctx.shadowColor = b.meta.color + '55';   // 33% opacity glow
    ctx.shadowBlur  = 12;

    // Draw bubble
    ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI*2);
    ctx.fillStyle   = b.meta.color + '22';   // 13% opacity fill
    ctx.strokeStyle = b.meta.color;          // solid stroke
    ctx.lineWidth   = 2;
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;

    // Factory labels inside bubble
    ctx.fillStyle = b.meta.color;
    ctx.font = 'bold 11px Inter,sans-serif';
    ctx.fillText(b.meta.short, b.x, b.y - 2);  // "F1"
    ctx.fillStyle = '#6B7280';
    ctx.font = '9px Inter,sans-serif';
    ctx.fillText(b.meta.name, b.x, b.y + 10);  // "Mumbai"
  });

  requestAnimationFrame(drawFrame);   // ~60fps loop
}
drawFrame();
```

**`lerp()` — Linear Interpolation:**
```javascript
function lerp(a, b, t) { return a + (b - a) * t; }
// t=0.018: each frame, bubble moves 1.8% of remaining distance to target
// This creates smooth gliding instead of instant jumps
```

---

## Part 2: D3.js Dual-Line Accuracy Chart

### Data Source

```javascript
const rawData    = {{ chart_data_json|safe }};
// Django injects: [{round:1, naive_global:0.61, clustered_accuracy:null, clustering_fired:false},
//                  {round:2, naive_global:0.63, ...}, ...,
//                  {round:10, naive_global:0.65, clustered_accuracy:0.79, clustering_fired:true}]
const clusterRnd = {{ cluster_round|default:"null" }};
// Django injects: 10 (or null if clustering hasn't fired)
```

### `initD3Chart(data)` — Full Chart Construction

```javascript
function initD3Chart(data) {
  d3.select('#d3-chart').selectAll('*').remove();   // clear on re-render

  // Calculate available width dynamically
  d3chartW = document.getElementById('d3-chart').offsetWidth - d3margin.left - d3margin.right;
  d3chartH = 140 - d3margin.top - d3margin.bottom;  // fixed height: 140px

  const svg = d3.select('#d3-chart').append('svg')
    .attr('width',  d3chartW + d3margin.left + d3margin.right)
    .attr('height', d3chartH + d3margin.top  + d3margin.bottom)
    .append('g').attr('transform', `translate(${d3margin.left},${d3margin.top})`);

  // X scale: rounds 1–20 (minimum 20)
  d3x = d3.scaleLinear()
    .domain([1, Math.max(20, d3.max(data, d => d.round))])
    .range([0, d3chartW]);

  // Y scale: 0–100%
  d3y = d3.scaleLinear().domain([0, 1]).range([d3chartH, 0]);

  // Horizontal grid lines
  svg.append('g').call(d3.axisLeft(d3y).ticks(4).tickSize(-d3chartW).tickFormat(''))
    .selectAll('line').style('stroke', '#F3F4F6');

  // Axes
  svg.append('g').attr('transform', `translate(0,${d3chartH})`)
    .call(d3.axisBottom(d3x).ticks(10).tickFormat(d => `R${d}`));
  svg.append('g').call(d3.axisLeft(d3y).ticks(4).tickFormat(d => `${(d*100).toFixed(0)}%`));
```

### Two Line Generators

```javascript
  // Gray dashed line: naive global (always drawn, even before clustering)
  d3lineGlobal = d3.line()
    .defined(d => d.naive_global != null)       // skip null points
    .x(d => d3x(d.round))
    .y(d => d3y(d.naive_global))
    .curve(d3.curveCatmullRom);                 // smooth curve

  // Green solid line: clustered accuracy (only after clustering fires)
  d3lineClustered = d3.line()
    .defined(d => d.clustering_fired && d.clustered_accuracy != null)
    .x(d => d3x(d.round))
    .y(d => d3y(d.clustered_accuracy))
    .curve(d3.curveCatmullRom);

  // Draw paths
  d3pathGlobal = svg.append('path').datum(data)
    .attr('fill', 'none').attr('stroke', '#9CA3AF').attr('stroke-width', 2)
    .attr('stroke-dasharray', '4,4')   // dashed = global baseline
    .attr('d', d3lineGlobal);

  d3pathClustered = svg.append('path').datum(data)
    .attr('fill', 'none').attr('stroke', '#10B981').attr('stroke-width', 2)  // green
    .attr('d', d3lineClustered);
```

### Animated Draw-On Effect

```javascript
  // Animate global line drawing left-to-right
  const tl = d3pathGlobal.node().getTotalLength();
  d3pathGlobal
    .attr('stroke-dashoffset', tl)                    // start fully hidden
    .transition().duration(1500).ease(d3.easeLinear)
    .attr('stroke-dashoffset', 0);                    // reveal over 1.5s
```

### Clustering Trigger Line

```javascript
  // Red dashed vertical line at the round clustering fired
  if (clusterRnd && data.find(d => d.round === clusterRnd)) {
    svg.append('line')
      .attr('x1', d3x(clusterRnd)).attr('x2', d3x(clusterRnd))
      .attr('y1', 0).attr('y2', d3chartH)
      .attr('stroke', '#EF4444').attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '4,3').attr('opacity', 0.7);
    svg.append('text')
      .attr('x', d3x(clusterRnd) + 3).attr('y', 12)
      .attr('fill', '#EF4444').attr('font-size', '9px').text('Clustering');
  }
```

---

## Part 3: WebSocket Event Handlers

```javascript
function connectWebSocket() {
  const ws = new WebSocket('ws://localhost:8000/ws');
  ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
```

### Handler: `round_complete`

```javascript
    if (data.type === 'round_complete') {
      // Update per-factory accuracy label
      const fe = document.getElementById('facc-' + data.factory_id);
      if (fe) fe.textContent = (data.accuracy * 100).toFixed(1) + '%';

      // Update round counter in page header
      const rn = document.getElementById('round-num');
      if (rn) rn.textContent = data.round_num;

      // Accumulate per-round accuracies (for potential future use)
      if (!window._ra) window._ra = {};
      if (!window._ra[data.round_num]) window._ra[data.round_num] = [];
      window._ra[data.round_num].push(data.accuracy);
    }
```

### Handler: `round_summary`

```javascript
    if (data.type === 'round_summary') {
      // Detect new training session (round_num = 1 but we have previous data)
      if (data.round_num === 1 && liveData.some(d => d.round > 1)) {
        liveData = [];    // reset live data
        // Also clear sidebar and D3 chart
      }

      // Update both accuracy stat cards
      const gStr = data.naive_global !== null ? (data.naive_global * 100).toFixed(1) + '%' : '—';
      const cStr = (data.clustering_fired && data.clustered_accuracy !== null)
        ? (data.clustered_accuracy * 100).toFixed(1) + '%' : '—';
      document.getElementById('m-global-acc').textContent = gStr;
      document.getElementById('m-acc').textContent = cStr;

      // Update sidebar (prepend row, keep max 5)
      // ... (see overview.html lines 479-501 for full row HTML)

      // Update D3 chart live
      const ex = liveData.find(d => d.round === data.round_num);
      if (ex) { ex.naive_global = data.naive_global; ... }
      else { liveData.push({round: data.round_num, ...}); liveData.sort(...); }

      if (d3svg) {
        d3pathGlobal.datum(liveData).transition().duration(300).attr('d', d3lineGlobal);
        d3pathClustered.datum(liveData).transition().duration(300).attr('d', d3lineClustered);
        // Re-draw dots after each update
      }
    }
```

### Handler: `cluster_assigned`

```javascript
    if (data.type === 'cluster_assigned') {
      // Update factory cluster badge
      const cb = document.getElementById('fcluster-' + data.factory_id);
      if (cb) {
        cb.textContent  = 'Cluster ' + data.cluster_id;
        cb.className    = 'badge-cluster-' + data.cluster_id;
      }

      // Create new cluster zone on canvas if it doesn't exist yet
      if (!clusterZones[String(data.cluster_id)]) {
        // Rebalance all zone x positions
        const existingKeys = Object.keys(clusterZones).filter(k => k !== 'center');
        existingKeys.push(String(data.cluster_id));
        existingKeys.forEach((k, i) => {
          const frac = (i + 1) / (existingKeys.length + 1);
          clusterZones[k] = { x: W * frac, y: H * 0.5, ... };
        });
      }

      // Move this factory's bubble to its new cluster zone
      const bub = bubbles.find(b => b.id === data.factory_id);
      if (bub) bub.cluster = String(data.cluster_id);
      // The lerp() in drawFrame() will smoothly animate the bubble to its new zone
    }
```

### Auto-Reconnect

```javascript
  ws.onclose = () => setTimeout(connectWebSocket, 5000);
  // If WebSocket drops, retry after 5 seconds
}
connectWebSocket();
```

---

## `addEventLog()` — Event Log Entry Builder

```javascript
function addEventLog(type, message) {
  const colors = {
    round:   ['var(--green-bg)',  'var(--green-2)'],  // green badge
    cluster: ['var(--coral-bg)', 'var(--coral)'],      // coral badge
    alert:   ['#FEE2E2',         '#DC2626']            // red badge
  };
  const [bg, fg] = colors[type] || colors.round;

  const time = now.getHours().toString().padStart(2,'0') + ':' + ...;  // HH:MM:SS

  const row = document.createElement('div');
  row.innerHTML = `
    <span>${time}</span>
    <span style="background:${bg};color:${fg};">${type}</span>
    <span>${message}</span>`;

  log.insertBefore(row, log.firstChild);    // newest at top
  while (log.children.length > 10)         // max 10 entries
    log.removeChild(log.lastChild);
}
```

**Called by:**
- `round_complete` handler: `addEventLog('round', 'Round 5 complete')`
- `cluster_assigned` handler: `addEventLog('cluster', 'Factory 1 moved to Cluster 0')`
