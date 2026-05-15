/**
 * MetricsPanel.js
 * Renders the right panel:
 *   1. Model Performance chart (SVG line chart)
 *   2. Perf stats (Global Accuracy, Training Loss, Convergence, Best Round)
 *   3. Cluster Status bars
 *   4. Recent Events list (delegates to EventList.js)
 */
(function (global) {
  'use strict';

  const CLUSTER_STYLES = [
    { label: 'Cluster 0', color: '#1A3D2B', barColor: '#2E5C42' },
    { label: 'Cluster 1', color: '#C04A20', barColor: '#E05C2F' },
    { label: 'Cluster 2', color: '#2563EB', barColor: '#93C5FD' },
    { label: 'Cluster 3', color: '#7C3AED', barColor: '#C4B5FD' },
  ];

  /* Build a lightweight SVG line chart */
  function _buildLineChart(chartData) {
    const W = 248, H = 130;
    const pad = { top: 10, right: 8, bottom: 20, left: 28 };
    const innerW = W - pad.left - pad.right;
    const innerH = H - pad.top  - pad.bottom;

    if (!chartData || chartData.length < 2) {
      return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
                <text x="${W/2}" y="${H/2}" text-anchor="middle" font-size="11" fill="#9CA3AF">No data</text>
              </svg>`;
    }

    const maxRound = Math.max(...chartData.map(d => d.round));
    const minAcc   = 0;
    const maxAcc   = 1;

    const xScale = r  => pad.left + (r / maxRound) * innerW;
    const yScale = ac => pad.top  + innerH - (ac - minAcc) / (maxAcc - minAcc) * innerH;

    const pts = chartData.map(d => `${xScale(d.round).toFixed(1)},${yScale(d.accuracy).toFixed(1)}`);
    const pathD = 'M ' + pts.join(' L ');

    // Area fill
    const first = chartData[0];
    const last  = chartData[chartData.length - 1];
    const areaD = `M ${xScale(first.round).toFixed(1)},${yScale(0).toFixed(1)} L ${pathD.slice(2)} L ${xScale(last.round).toFixed(1)},${yScale(0).toFixed(1)} Z`;

    // Y-axis labels
    const yLabels = [0, 0.25, 0.50, 0.75, 1.00].map(v => ({
      y: yScale(v),
      label: Math.round(v * 100) + '%',
    }));

    // X-axis labels
    const xTicks = [0, Math.round(maxRound * 0.25), Math.round(maxRound * 0.5), Math.round(maxRound * 0.75), maxRound];

    return `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="perfGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stop-color="#1A3D2B" stop-opacity="0.12"/>
            <stop offset="100%" stop-color="#1A3D2B" stop-opacity="0"/>
          </linearGradient>
        </defs>

        <!-- Y grid lines -->
        ${yLabels.map(l => `
          <line x1="${pad.left}" y1="${l.y.toFixed(1)}" x2="${W - pad.right}" y2="${l.y.toFixed(1)}"
                stroke="#C8C3B8" stroke-width="1" stroke-dasharray="3,3"/>
          <text x="${pad.left - 4}" y="${(l.y + 3).toFixed(1)}" text-anchor="end"
                font-size="8" fill="#6B6B5E" font-family="DM Mono, monospace">${l.label}</text>
        `).join('')}

        <!-- Area -->
        <path d="${areaD}" fill="url(#perfGrad)"/>

        <!-- Line -->
        <path d="${pathD}" fill="none" stroke="#1A3D2B" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round"/>

        <!-- X labels -->
        ${xTicks.map(r => `
          <text x="${xScale(r).toFixed(1)}" y="${H - 4}" text-anchor="middle"
                font-size="8" fill="#6B6B5E" font-family="DM Mono, monospace">${r}</text>
        `).join('')}
      </svg>
    `;
  }

  /**
   * @param {HTMLElement} container  — #topo-panel
   * @param {object}      data       — { chartData, metrics, clusters, events }
   */
  function renderMetricsPanel(container, data) {
    const { chartData = [], metrics = {}, clusters = {}, events = [] } = data;

    const globalAcc   = metrics.global_accuracy   != null ? (metrics.global_accuracy   * 100).toFixed(1) + '%' : '—';
    const trainLoss   = metrics.training_loss      != null ? metrics.training_loss.toFixed(3)                   : '—';
    const convergence = metrics.convergence_rate   != null ? (metrics.convergence_rate  * 100).toFixed(1) + '%' : '—';
    const bestRound   = metrics.best_round         != null ? metrics.best_round                                 : '—';

    const clusterKeys = Object.keys(clusters).filter(k => k !== 'unassigned');
    const unassignedCount = (clusters['unassigned'] || []).length;

    /* Build cluster accuracy per cluster (average of node accuracies) */
    const clusterStats = clusterKeys.map((key, idx) => {
      const nodes = clusters[key] || [];
      const avg   = nodes.length > 0
        ? nodes.reduce((s, n) => s + (n.accuracy || 0), 0) / nodes.length
        : 0;
      const style = CLUSTER_STYLES[idx] || CLUSTER_STYLES[0];
      return { key, label: style.label, color: style.barColor, pct: avg };
    });

    container.innerHTML = `

      <!-- Performance Chart Card -->
      <div class="panel-card">
        <div class="panel-card-title">Model Performance</div>
        <div id="perf-chart-container">
          ${_buildLineChart(chartData)}
        </div>
        <div class="perf-stats">
          ${global.StatCard.html('Global Accuracy', globalAcc, '#059669')}
          ${global.StatCard.html('Training Loss',   trainLoss)}
          ${global.StatCard.html('Convergence',     convergence)}
          ${global.StatCard.html('Best Round',      bestRound)}
        </div>
      </div>

      <!-- Cluster Status Card -->
      <div class="panel-card">
        <div class="panel-card-title">Cluster Status</div>
        ${clusterStats.map((cs, i) => `
          <div class="cluster-row">
            <div class="cr-dot" style="background:${CLUSTER_STYLES[i].color}"></div>
            <div class="cr-name">${cs.label}</div>
            <div class="cr-bar-bg">
              <div class="cr-bar-fill"
                   style="width:${(cs.pct * 100).toFixed(1)}%; background:${cs.color}">
              </div>
            </div>
            <div class="cr-pct">${(cs.pct * 100).toFixed(1)}%</div>
          </div>
        `).join('')}

        ${unassignedCount > 0 ? `
          <div class="unassigned-row" style="margin-top:6px">
            <div class="cr-dot" style="background:#94A3B8"></div>
            <div class="cr-name" style="color:#9CA3AF">Unassigned</div>
            <div class="ua-dash"></div>
            <div class="ua-count">${unassignedCount}</div>
          </div>
        ` : ''}
      </div>

      <!-- Recent Events Card -->
      <div class="panel-card">
        <div class="panel-card-title">Recent Events</div>
        <div id="event-list-container"></div>
      </div>
    `;

    /* Delegate event list rendering */
    const evEl = container.querySelector('#event-list-container');
    if (evEl && global.EventList) global.EventList.render(evEl, events);
  }

  global.MetricsPanel = { render: renderMetricsPanel };
})(window);
