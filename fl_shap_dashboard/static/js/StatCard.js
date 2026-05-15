/**
 * StatCard.js
 * Renders a single key-value stat card inside a parent element.
 * Used by MetricsPanel.js.
 */
(function (global) {
  'use strict';

  /**
   * @param {string} key    — label text
   * @param {string} value  — primary value
   * @param {string} [color] — optional CSS color for value
   * @returns {string} HTML string
   */
  function statCardHTML(key, value, color) {
    const colorStyle = color ? `style="color:${color}"` : '';
    return `
      <div class="perf-stat-key">${key}</div>
      <div class="perf-stat-val" ${colorStyle}>${value}</div>
    `;
  }

  global.StatCard = { html: statCardHTML };
})(window);
