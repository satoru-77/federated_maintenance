/**
 * Sidebar.js
 * Renders the left fixed sidebar: logo, navigation, simulation info.
 * Pure vanilla JS — no framework dependency.
 */
(function (global) {
  'use strict';

  const NAV_ITEMS = [
    {
      id: 'topology', label: 'Topology', sub: 'Live network view',
      href: '/topology/',
      icon: `<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
               <circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/>
               <circle cx="19" cy="19" r="2"/>
               <line x1="12" y1="7" x2="5" y2="17"/>
               <line x1="12" y1="7" x2="19" y2="17"/>
               <line x1="7" y1="19" x2="17" y2="19"/>
             </svg>`
    },
    {
      id: 'training', label: 'Training', sub: 'Model training status',
      href: '/rounds/',
      icon: `<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
               <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
             </svg>`
    },
    {
      id: 'analytics', label: 'Analytics', sub: 'Performance metrics',
      href: '/explainability/',
      icon: `<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
               <line x1="18" y1="20" x2="18" y2="10"/>
               <line x1="12" y1="20" x2="12" y2="4"/>
               <line x1="6"  y1="20" x2="6"  y2="14"/>
             </svg>`
    },
    {
      id: 'settings', label: 'Settings', sub: 'Simulation settings',
      href: '/simulation/',
      icon: `<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
               <circle cx="12" cy="12" r="3"/>
               <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06
                        a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09
                        A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06
                        a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15
                        a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09
                        A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06
                        a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68
                        a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09
                        a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06
                        a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9
                        a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09
                        a1.65 1.65 0 0 0-1.51 1z"/>
             </svg>`
    },
  ];

  /**
   * @param {HTMLElement} container  — the sidebar DOM element
   * @param {object}      simInfo   — { round, total_rounds, nodes, clusters, accuracy, convergence, status }
   * @param {string}      activeId  — nav item id that is active ('topology')
   */
  function renderSidebar(container, simInfo, activeId) {
    container.innerHTML = `

      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="sidebar-logo-icon">
          <svg fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="12" cy="5" r="2"/>
            <circle cx="5" cy="19" r="2"/>
            <circle cx="19" cy="19" r="2"/>
            <line x1="12" y1="7" x2="5" y2="17"/>
            <line x1="12" y1="7" x2="19" y2="17"/>
          </svg>
        </div>
        <div>
          <div class="sidebar-logo-name">FedPredict</div>
          <div class="sidebar-logo-sub">/ topology view</div>
        </div>
      </div>

      <!-- Navigation -->
      <div class="sidebar-section-label">Navigation</div>
      <nav class="sidebar-nav">
        ${NAV_ITEMS.map(item => `
          <a href="${item.href}" class="sidebar-nav-item ${item.id === activeId ? 'active' : ''}">
            <span class="nav-icon">${item.icon}</span>
            <div>
              <div class="nav-label">${item.label}</div>
              <div class="nav-label-sub">${item.sub}</div>
            </div>
          </a>
        `).join('')}
      </nav>

      <!-- Simulation Info -->
      <div class="sidebar-section-label" style="margin-top:8px">Simulation Info</div>
      <div class="sim-info">
        <div class="sim-info-row">
          <span class="sim-info-key">Round</span>
          <span class="sim-info-val" id="si-round">
            ${simInfo.round || '—'}/${simInfo.total_rounds || '—'}
          </span>
        </div>
        <div class="sim-info-row">
          <span class="sim-info-key">Nodes</span>
          <span class="sim-info-val" id="si-nodes">${simInfo.nodes || '—'}</span>
        </div>
        <div class="sim-info-row">
          <span class="sim-info-key">Clusters</span>
          <span class="sim-info-val" id="si-clusters">${simInfo.clusters || '—'}</span>
        </div>
        <div class="sim-info-row">
          <span class="sim-info-key">Global Accuracy</span>
          <span class="sim-info-val" id="si-acc">
            ${simInfo.accuracy != null ? (simInfo.accuracy * 100).toFixed(1) + '%' : '—'}
          </span>
        </div>
        <div class="sim-info-row">
          <span class="sim-info-key">Convergence</span>
          <span class="sim-info-val" id="si-conv">
            ${simInfo.convergence != null ? (simInfo.convergence * 100).toFixed(1) + '%' : '—'}
          </span>
        </div>
        <div class="sim-info-row">
          <span class="sim-info-key">Status</span>
          <span class="sim-info-val">
            <span class="sim-status-dot"></span>
            <span id="si-status">${simInfo.status || 'Running'}</span>
          </span>
        </div>
      </div>

      <!-- Footer -->
      <div class="sidebar-footer">
        <button class="btn-customize" onclick="alert('Simulation config coming soon')">
          Customize →
        </button>
        <button class="btn-reset" onclick="alert('Reset? (not implemented)')">
          <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <polyline points="1 4 1 10 7 10"/>
            <path d="M3.51 15a9 9 0 1 0 .49-3.36"/>
          </svg>
          Reset Simulation
        </button>
      </div>
    `;
  }

  global.Sidebar = { render: renderSidebar };
})(window);
