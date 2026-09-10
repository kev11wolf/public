// charts.js — Lightweight Canvas S-curve rendering + accessible data table
// No external dependencies. Renders planned/forecast/actual cumulative % series.

const COLORS = {
  planned: '#5b7fb0',
  forecast: '#c98a2b',
  actual: '#2f9e5b',
  grid: '#e2e6ea',
  axis: '#8a94a3',
};

export function drawSCurve(canvas, series, opts = {}) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(rect.width, 300);
  const height = opts.height || 260;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.height = height + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 16, right: 16, bottom: 32, left: 44 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const maxLen = Math.max(1, ...series.map((s) => s.points.length));
  const maxY = 100;

  ctx.strokeStyle = COLORS.grid;
  ctx.fillStyle = COLORS.axis;
  ctx.font = '11px system-ui, sans-serif';
  ctx.lineWidth = 1;
  for (let g = 0; g <= 100; g += 25) {
    const y = padding.top + plotH - (g / maxY) * plotH;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(padding.left + plotW, y);
    ctx.stroke();
    ctx.fillText(g + '%', 4, y + 3);
  }

  series.forEach((s) => {
    if (!s.points.length) return;
    ctx.strokeStyle = s.color || COLORS[s.key] || '#333';
    ctx.lineWidth = 2;
    ctx.beginPath();
    s.points.forEach((p, i) => {
      const x = padding.left + (i / Math.max(1, maxLen - 1)) * plotW;
      const y = padding.top + plotH - (p.y / maxY) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  const labelSeries = series.find((s) => s.points.length) || { points: [] };
  const idxs = [0, Math.floor((labelSeries.points.length - 1) / 2), labelSeries.points.length - 1].filter((v, i, a) => a.indexOf(v) === i && v >= 0);
  ctx.fillStyle = COLORS.axis;
  idxs.forEach((i) => {
    const p = labelSeries.points[i];
    if (!p) return;
    const x = padding.left + (i / Math.max(1, maxLen - 1)) * plotW;
    ctx.fillText(p.label || '', Math.max(padding.left, x - 20), height - 8);
  });
}

export function buildLegendHtml(series) {
  return series
    .map((s) => '<span class="legend-item"><span class="legend-swatch" style="background:' + (s.color || COLORS[s.key]) + '"></span>' + s.name + '</span>')
    .join('');
}

export function renderChartDataTable(container, series, dateLabels) {
  container.innerHTML = '';
  const table = document.createElement('table');
  table.className = 'chart-data-table';
  table.setAttribute('aria-label', 'Time-phased progress data table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  const thDate = document.createElement('th');
  thDate.textContent = 'Period';
  headRow.appendChild(thDate);
  series.forEach((s) => {
    const th = document.createElement('th');
    th.textContent = s.name;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  dateLabels.forEach((label, i) => {
    const row = document.createElement('tr');
    const tdLabel = document.createElement('td');
    tdLabel.textContent = label;
    row.appendChild(tdLabel);
    series.forEach((s) => {
      const td = document.createElement('td');
      const pt = s.points[i];
      td.textContent = pt ? pt.y.toFixed(1) + '%' : '—';
      row.appendChild(td);
    });
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}
