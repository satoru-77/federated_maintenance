/**
 * ClusterGraph.js
 * Canvas-based cluster visualization:
 *   - Grid background
 *   - Cluster blobs (filled circles)
 *   - Node circles with floating animation
 *   - Spoke lines from node → cluster center
 *   - Dashed inter-cluster lines
 *   - Hover tooltip
 */
(function (global) {
  'use strict';

  /* ── Cluster style palette ──────────────────────────────── */
  const CLUSTER_STYLES = [
    { fill: 'rgba(26,61,43,0.10)',   stroke: '#2E5C42', nodeColor: '#1A3D2B', centerColor: '#0D2218', label: 'Cluster 0' },
    { fill: 'rgba(224,92,47,0.10)',  stroke: '#E05C2F', nodeColor: '#C04A20', centerColor: '#8B3015', label: 'Cluster 1' },
    { fill: 'rgba(37,99,235,0.10)',  stroke: '#93C5FD', nodeColor: '#2563EB', centerColor: '#1D4ED8', label: 'Cluster 2' },
    { fill: 'rgba(124,58,237,0.10)', stroke: '#C4B5FD', nodeColor: '#7C3AED', centerColor: '#5B21B6', label: 'Cluster 3' },
    { fill: 'rgba(140,184,154,0.15)',stroke: '#8CB89A', nodeColor: '#2E5C42', centerColor: '#1A3D2B', label: 'Unassigned' },
  ];

  /* ── Default cluster layout (positions in unit-canvas 0–1) ── */
  const DEFAULT_CLUSTER_POSITIONS = [
    { cx: 0.28, cy: 0.32 },
    { cx: 0.68, cy: 0.28 },
    { cx: 0.25, cy: 0.68 },
    { cx: 0.70, cy: 0.65 },
  ];

  /* Seeded pseudo-random so layout is stable between frames */
  function seededRand(seed) {
    let s = seed;
    return function () {
      s = (s * 1664525 + 1013904223) & 0xffffffff;
      return (s >>> 0) / 0xffffffff;
    };
  }

  /* Build internal scene from raw cluster data */
  function buildScene(clusters) {
    const keys = Object.keys(clusters).filter(k => k !== 'unassigned');
    const scene = { clusters: [], unassigned: [] };

    keys.forEach((key, idx) => {
      const pos   = DEFAULT_CLUSTER_POSITIONS[idx] || { cx: 0.5, cy: 0.5 };
      const style = CLUSTER_STYLES[idx] || CLUSTER_STYLES[0];
      const nodes = clusters[key] || [];
      const rand  = seededRand(idx * 1337 + 7);

      const spoke = nodes.map((n, ni) => {
        const angle = (2 * Math.PI * ni) / nodes.length + rand() * 0.4;
        const dist  = 0.07 + rand() * 0.06;
        return {
          id:       n.factory_id || ni,
          name:     n.name || `Node ${n.factory_id}`,
          accuracy: n.accuracy,
          dx: Math.cos(angle) * dist,   // relative to cluster center (0–1 space)
          dy: Math.sin(angle) * dist,
          phaseOffset: rand() * Math.PI * 2,
          animRadius: 0.003 + rand() * 0.003,
        };
      });

      scene.clusters.push({
        key, label: style.label, style, pos,
        blobRadius: 0.12 + nodes.length * 0.008,
        nodes: spoke,
      });
    });

    // Unassigned nodes (shown at center with grey style)
    const ua = clusters['unassigned'] || [];
    const rand = seededRand(999);
    scene.unassigned = ua.map((n, i) => ({
      id:   n.factory_id || i,
      name: n.name || `Node ${n.factory_id}`,
      style: CLUSTER_STYLES[4],
      px: 0.48 + (rand() - 0.5) * 0.06,
      py: 0.50 + (rand() - 0.5) * 0.06,
      phaseOffset: rand() * Math.PI * 2,
    }));

    return scene;
  }

  /* ────────────────────────────────────────────────────────── */
  class ClusterGraph {
    constructor(canvas, tooltipEl, clusters) {
      this.canvas   = canvas;
      this.ctx      = canvas.getContext('2d');
      this.tooltip  = tooltipEl;
      this.scene    = buildScene(clusters);
      this.t        = 0;
      this.hovered  = null;
      this._raf     = null;

      this._bindEvents();
      this._startLoop();
    }

    /* Resize canvas to its CSS size */
    resize() {
      const r   = this.canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      this.canvas.width  = r.width  * dpr;
      this.canvas.height = r.height * dpr;
      // Reset transform before re-applying DPI scale to avoid cumulative drift
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(dpr, dpr);
    }

    /* Convert 0–1 unit coords to canvas pixel coords */
    _px(ux) { return ux * this.canvas.clientWidth; }
    _py(uy) { return uy * this.canvas.clientHeight; }

    /* ── Drawing ─────────────────────────────────────────── */
    _drawGrid(ctx) {
      const w = this.canvas.clientWidth;
      const h = this.canvas.clientHeight;
      const step = 30;
      ctx.save();
      ctx.strokeStyle = 'rgba(229,231,235,0.6)';
      ctx.lineWidth   = 1;
      for (let x = 0; x < w; x += step) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = 0; y < h; y += step) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
      ctx.restore();
    }

    _drawInterClusterLines(ctx) {
      const cl = this.scene.clusters;
      ctx.save();
      ctx.setLineDash([6, 6]);
      ctx.strokeStyle = 'rgba(156,163,175,0.55)';
      ctx.lineWidth   = 1;
      for (let i = 0; i < cl.length - 1; i++) {
        const ax = this._px(cl[i].pos.cx);
        const ay = this._py(cl[i].pos.cy);
        const bx = this._px(cl[i + 1].pos.cx);
        const by = this._py(cl[i + 1].pos.cy);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      }
      ctx.restore();
    }

    _drawCluster(ctx, cluster, t) {
      const cx = this._px(cluster.pos.cx);
      const cy = this._py(cluster.pos.cy);
      const br = this._px(cluster.blobRadius);
      const st = cluster.style;

      /* Blob fill */
      ctx.beginPath();
      ctx.arc(cx, cy, br, 0, Math.PI * 2);
      ctx.fillStyle   = st.fill;
      ctx.fill();
      ctx.strokeStyle = st.stroke;
      ctx.lineWidth   = 1;
      ctx.stroke();

      /* Center node */
      ctx.beginPath();
      ctx.arc(cx, cy, 10, 0, Math.PI * 2);
      ctx.fillStyle   = st.centerColor;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth   = 2;
      ctx.stroke();

      /* Cluster label */
      ctx.font      = '600 11px Inter, sans-serif';
      ctx.fillStyle = st.nodeColor;
      ctx.textAlign = 'left';
      ctx.fillText(cluster.label, cx - br + 6, cy + br - 10);
      ctx.font      = '400 9px Inter, sans-serif';
      ctx.fillStyle = st.nodeColor;
      ctx.fillText(`${cluster.nodes.length} nodes`, cx - br + 6, cy + br - 0);

      /* Spoke lines + nodes */
      cluster.nodes.forEach(node => {
        const floatY = Math.sin(t * 0.8 + node.phaseOffset) * this._py(node.animRadius);
        const nx = cx + this._px(node.dx);
        const ny = cy + this._py(node.dy) + floatY;

        /* Spoke */
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(nx, ny);
        ctx.strokeStyle = st.stroke;
        ctx.lineWidth   = 1;
        ctx.setLineDash([]);
        ctx.stroke();

        /* Node circle */
        const isHovered = this.hovered && this.hovered.id === node.id;
        const radius    = isHovered ? 8 : 6;
        ctx.beginPath();
        ctx.arc(nx, ny, radius, 0, Math.PI * 2);
        ctx.fillStyle   = isHovered ? st.centerColor : st.nodeColor;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth   = 1.5;
        ctx.stroke();
      });
    }

    _drawUnassigned(ctx, t) {
      this.scene.unassigned.forEach(node => {
        const floatY = Math.sin(t * 0.6 + node.phaseOffset) * 2;
        const nx = this._px(node.px);
        const ny = this._py(node.py) + floatY;
        ctx.beginPath();
        ctx.arc(nx, ny, 5, 0, Math.PI * 2);
        ctx.fillStyle   = node.style.nodeColor;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth   = 1.5;
        ctx.stroke();
      });
    }

    _frame(ts) {
      this.t = ts / 1000;
      const ctx = this.ctx;
      const w   = this.canvas.clientWidth;
      const h   = this.canvas.clientHeight;

      ctx.clearRect(0, 0, w, h);
      this._drawGrid(ctx);
      this._drawInterClusterLines(ctx);
      this.scene.clusters.forEach(cl => this._drawCluster(ctx, cl, this.t));
      this._drawUnassigned(ctx, this.t);

      this._raf = requestAnimationFrame(ts => this._frame(ts));
    }

    _startLoop() {
      this.resize();
      this._raf = requestAnimationFrame(ts => this._frame(ts));
    }

    /* ── Hit-testing ─────────────────────────────────────── */
    _hitTest(mx, my) {
      for (const cl of this.scene.clusters) {
        const cx = this._px(cl.pos.cx);
        const cy = this._py(cl.pos.cy);
        for (const node of cl.nodes) {
          const floatY = Math.sin(this.t * 0.8 + node.phaseOffset) * this._py(node.animRadius);
          const nx = cx + this._px(node.dx);
          const ny = cy + this._py(node.dy) + floatY;
          if ((mx - nx) ** 2 + (my - ny) ** 2 < 12 ** 2) {
            return { ...node, clusterLabel: cl.label, style: cl.style };
          }
        }
      }
      return null;
    }

    _bindEvents() {
      const canvas = this.canvas;
      const tt     = this.tooltip;

      canvas.addEventListener('mousemove', e => {
        const rect = canvas.getBoundingClientRect();
        const mx   = e.clientX - rect.left;
        const my   = e.clientY - rect.top;
        const hit  = this._hitTest(mx, my);
        this.hovered = hit;
        if (hit) {
          canvas.style.cursor = 'pointer';
          tt.innerHTML = `
            <div class="tt-title">${hit.name}</div>
            <div class="tt-row">${hit.clusterLabel}</div>
            ${hit.accuracy != null ? `<div class="tt-row">Accuracy: ${(hit.accuracy * 100).toFixed(1)}%</div>` : ''}
          `;
          tt.classList.add('visible');
          // Position: offset from canvas edge
          let left = e.clientX - rect.left + 14;
          let top  = e.clientY - rect.top  - 10;
          if (left + 140 > rect.width)  left -= 160;
          if (top  + 60  > rect.height) top  -= 70;
          tt.style.left = left + 'px';
          tt.style.top  = top  + 'px';
        } else {
          canvas.style.cursor = 'grab';
          tt.classList.remove('visible');
        }
      });

      canvas.addEventListener('mouseleave', () => {
        this.hovered = null;
        tt.classList.remove('visible');
      });

      window.addEventListener('resize', () => this.resize());
    }

    destroy() {
      if (this._raf) cancelAnimationFrame(this._raf);
    }
  }

  global.ClusterGraph = ClusterGraph;
})(window);
