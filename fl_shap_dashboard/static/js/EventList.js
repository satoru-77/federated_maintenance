/**
 * EventList.js
 * Renders the "Recent Events" list inside a container element.
 */
(function (global) {
  'use strict';

  const CLUSTER_COLORS = {
    1: '#7C3AED',  // purple
    2: '#059669',  // green
    3: '#2563EB',  // blue
    4: '#DB2777',  // pink
    null: '#94A3B8',
    undefined: '#94A3B8',
  };

  function _relTime(isoStr) {
    if (!isoStr) return '';
    try {
      const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
      if (diff < 60)    return Math.round(diff) + 's ago';
      if (diff < 3600)  return Math.round(diff / 60) + 'm ago';
      return Math.round(diff / 3600) + 'h ago';
    } catch { return ''; }
  }

  /**
   * @param {HTMLElement} container
   * @param {Array}       events  — array of { text, cluster_id, timestamp }
   */
  function renderEventList(container, events) {
    if (!events || events.length === 0) {
      container.innerHTML = '<div style="font-size:11px;color:#9CA3AF;padding:6px 0">No recent events</div>';
      return;
    }

    container.innerHTML = events.slice(0, 8).map(ev => {
      const color = CLUSTER_COLORS[ev.cluster_id] || '#94A3B8';
      return `
        <div class="event-item">
          <div class="ev-dot" style="background:${color}"></div>
          <div class="ev-text">${ev.text || ev.message || 'Event'}</div>
          <div class="ev-time">${_relTime(ev.timestamp)}</div>
        </div>
      `;
    }).join('');
  }

  global.EventList = { render: renderEventList };
})(window);
