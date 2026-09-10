// ui.js — Rendering and interaction logic for all app screens.
import {
  uuid, nowIso, clampPct, CURVE_TYPES, CURVE_LABELS, REPORTING_PERIODS, PERIOD_STATUS,
  makeProgram, makeBuilding, makeContract, makeActivity, makeGate, makeActualHourRecord,
  makeAuditEvent, validateGateWeights, GATE_WEIGHT_TOLERANCE,
} from './schema.js';
import {
  activityPlannedPct, activityForecastPct, activityActualPct, activityCalculatedActualPct,
  plannedValue, forecastValue, earnedValue, earnedHours, sumActualHours,
  rollupTotals, computeSPI, computeLPI, formatRatio, ratioStatus, progressPctAtDate,
  timePhasedSeries,
} from './calculations.js';
import { getOpenPeriod, getOrCreateOpenPeriod, closePeriodAndAdvance, reopenPeriod, isDateInPeriod, periodBoundaryDates } from './periods.js';
import { drawSCurve, renderChartDataTable, buildLegendHtml } from './charts.js';
import { saveDataset, exportDatasetToFile, parseImportedJson } from './store.js';
import { buildSampleDataset } from './sample-data.js';

export function createApp(root, initialDataset) {
  const state = {
    ds: initialDataset,
    tab: 'dashboard',
    selection: {},
  };

  function fmtMoney(v) {
    try {
      return new Intl.NumberFormat(state.ds.settings.locale || 'en-US', {
        style: 'currency',
        currency: state.ds.settings.reportingCurrency || 'USD',
        maximumFractionDigits: 0,
      }).format(v || 0);
    } catch (e) {
      return '$' + Math.round(v || 0).toLocaleString();
    }
  }
  function fmtHours(v) {
    return (v || 0).toLocaleString(state.ds.settings.locale || 'en-US', { maximumFractionDigits: 1 });
  }
  function fmtPct(v) {
    return (v || 0).toFixed(1) + '%';
  }
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }
  function admin() {
    return state.ds.settings.adminName || 'Admin';
  }
  function asOfDate() {
    return state.ds.settings.statusDate;
  }

  async function persist() {
    await saveDataset(state.ds);
  }

  function audit(entityType, entityId, eventType, before, after, reason) {
    state.ds.auditEvents.push(
      makeAuditEvent({ entityType, entityId, eventType, before, after, reason, periodId: currentOpenPeriodId(), performedBy: admin() })
    );
  }

  function currentOpenPeriodId() {
    const p = getOpenPeriod(state.ds.periods);
    return p ? p.id : null;
  }

  function ensureOpenPeriod() {
    return getOrCreateOpenPeriod(state.ds.periods, state.ds.settings.reportingPeriod, state.ds.settings.statusDate);
  }

  function isEditBlocked(dateIso) {
    const open = getOpenPeriod(state.ds.periods);
    if (!open) return false;
    if (!dateIso) return false;
    return !isDateInPeriod(dateIso, open) && dateIso < open.startDate;
  }

  // ---------- Metrics ----------

  function gatesForActivity(activityId) {
    return state.ds.gates.filter((g) => g.activityId === activityId).sort((a, b) => (a.order || 0) - (b.order || 0));
  }
  function hoursForActivity(activityId) {
    return state.ds.actualHours.filter((h) => h.activityId === activityId);
  }
  function activitiesForContract(contractId) {
    return state.ds.activities.filter((a) => a.contractId === contractId);
  }
  function contractsForBuilding(buildingId) {
    return state.ds.contracts.filter((c) => c.buildingId === buildingId);
  }
  function buildingsForProgram(programId) {
    return state.ds.buildings.filter((b) => b.programId === programId);
  }

  function activityMetrics(activity) {
    const gates = gatesForActivity(activity.id);
    const hours = hoursForActivity(activity.id);
    const plannedPct = activityPlannedPct(activity, asOfDate());
    const forecastPct = activityForecastPct(activity, asOfDate());
    const calcActualPct = activityCalculatedActualPct(gates);
    const actualPct = activityActualPct(activity, gates);
    const pv = activity.budget * (plannedPct / 100);
    const fv = activity.budget * (forecastPct / 100);
    const ev = activity.budget * (actualPct / 100);
    const eh = activity.plannedHours * (actualPct / 100);
    const ah = sumActualHours(hours);
    const spi = computeSPI(ev, pv);
    const lpi = computeLPI(eh, ah);
    return {
      plannedPct, forecastPct, actualPct, calcActualPct,
      plannedValue: pv, forecastValue: fv, earnedValue: ev, earnedHours: eh, actualHours: ah,
      budget: activity.budget, plannedHours: activity.plannedHours,
      spi, lpi,
      gateWeightCheck: validateGateWeights(gates),
    };
  }

  function contractMetrics(contract) {
    const acts = activitiesForContract(contract.id).map(activityMetrics);
    return rollupTotals(acts);
  }
  function buildingMetrics(building) {
    const contracts = contractsForBuilding(building.id).map(contractMetrics);
    return rollupTotals(contracts);
  }
  function programMetrics(program) {
    const buildings = buildingsForProgram(program.id).map(buildingMetrics);
    return rollupTotals(buildings);
  }

  // ---------- Shell / navigation ----------

  const TABS = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'structure', label: 'Program Structure' },
    { id: 'activities', label: 'Activities' },
    { id: 'hours', label: 'Hours' },
    { id: 'periods', label: 'Reporting Periods' },
    { id: 'settings', label: 'Settings / Data' },
  ];

  function renderShell() {
    root.innerHTML = '';
    const header = document.createElement('header');
    header.className = 'app-header';
    header.innerHTML =
      '<div class="brand"><span class="brand-mark">CPT</span><span class="brand-name">Contract Progress Tracker</span></div>' +
      '<div class="header-meta"><span class="status-pill" id="open-period-pill"></span></div>';
    root.appendChild(header);

    const nav = document.createElement('nav');
    nav.className = 'app-nav';
    nav.setAttribute('role', 'tablist');
    TABS.forEach((t) => {
      const btn = document.createElement('button');
      btn.className = 'nav-btn' + (state.tab === t.id ? ' active' : '');
      btn.textContent = t.label;
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-selected', state.tab === t.id ? 'true' : 'false');
      btn.addEventListener('click', () => {
        state.tab = t.id;
        render();
      });
      nav.appendChild(btn);
    });
    root.appendChild(nav);

    const main = document.createElement('main');
    main.className = 'app-main';
    main.id = 'app-main';
    root.appendChild(main);

    const openPill = header.querySelector('#open-period-pill');
    const open = getOpenPeriod(state.ds.periods);
    openPill.textContent = open ? 'Open period: ' + open.label + ' (' + open.startDate + ' to ' + open.endDate + ')' : 'No open period';
  }

  function mainEl() {
    return document.getElementById('app-main');
  }

  function render() {
    renderShell();
    const main = mainEl();
    if (state.tab === 'dashboard') renderDashboard(main);
    else if (state.tab === 'structure') renderStructure(main);
    else if (state.tab === 'activities') renderActivities(main);
    else if (state.tab === 'activityDetail') renderActivityDetail(main);
    else if (state.tab === 'hours') renderHours(main);
    else if (state.tab === 'periods') renderPeriods(main);
    else if (state.tab === 'settings') renderSettings(main);
  }

  // ---------- KPI card helper ----------
  function kpiCard(label, value, statusClass) {
    const div = document.createElement('div');
    div.className = 'kpi-card' + (statusClass ? ' kpi-' + statusClass : '');
    div.innerHTML = '<div class="kpi-label">' + esc(label) + '</div><div class="kpi-value">' + esc(value) + '</div>';
    return div;
  }

  // ---------- Dashboard ----------
  function renderDashboard(main) {
    ensureOpenPeriod();
    const program = state.ds.programs[0];
    main.innerHTML = '';

    const controls = document.createElement('div');
    controls.className = 'panel controls-row';
    controls.innerHTML =
      '<label>Status date <input type="date" id="status-date" value="' + esc(asOfDate()) + '"></label>' +
      '<label>Reporting period ' +
      '<select id="period-toggle">' +
      '<option value="weekly"' + (state.ds.settings.reportingPeriod === 'weekly' ? ' selected' : '') + '>Weekly</option>' +
      '<option value="monthly"' + (state.ds.settings.reportingPeriod === 'monthly' ? ' selected' : '') + '>Monthly</option>' +
      '</select></label>' +
      '<label>Program <select id="program-select"></select></label>';
    main.appendChild(controls);

    const progSelect = controls.querySelector('#program-select');
    state.ds.programs.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      progSelect.appendChild(opt);
    });
    if (state.selection.programId) progSelect.value = state.selection.programId;
    const activeProgram = state.ds.programs.find((p) => p.id === progSelect.value) || program;

    controls.querySelector('#status-date').addEventListener('change', (e) => {
      state.ds.settings.statusDate = e.target.value;
      persist().then(render);
    });
    controls.querySelector('#period-toggle').addEventListener('change', (e) => {
      state.ds.settings.reportingPeriod = e.target.value;
      persist().then(render);
    });
    progSelect.addEventListener('change', (e) => {
      state.selection.programId = e.target.value;
      render();
    });

    if (!activeProgram) {
      const empty = document.createElement('div');
      empty.className = 'panel';
      empty.innerHTML = '<p>No program exists yet. Go to <strong>Program Structure</strong> to create one, or load sample data from <strong>Settings / Data</strong>.</p>';
      main.appendChild(empty);
      return;
    }

    const metrics = programMetrics(activeProgram);
    const kpiRow = document.createElement('div');
    kpiRow.className = 'kpi-row';
    kpiRow.appendChild(kpiCard('Budget', fmtMoney(metrics.budget)));
    kpiRow.appendChild(kpiCard('Planned %', fmtPct(metrics.plannedPct)));
    kpiRow.appendChild(kpiCard('Forecast %', fmtPct(metrics.forecastPct)));
    kpiRow.appendChild(kpiCard('Actual %', fmtPct(metrics.actualPct)));
    kpiRow.appendChild(kpiCard('Variance (Actual-Planned)', fmtPct(metrics.actualPct - metrics.plannedPct), (metrics.actualPct - metrics.plannedPct) >= 0 ? 'good' : 'bad'));
    kpiRow.appendChild(kpiCard('Cumulative SPI', formatRatio(metrics.spi), ratioStatus(metrics.spi)));
    kpiRow.appendChild(kpiCard('Cumulative LPI', formatRatio(metrics.lpi), ratioStatus(metrics.lpi)));
    main.appendChild(kpiRow);

    const chartPanel = document.createElement('div');
    chartPanel.className = 'panel';
    chartPanel.innerHTML = '<h2>Program S-Curve (' + esc(activeProgram.name) + ')</h2><div class="legend" id="chart-legend"></div><canvas id="scurve-canvas" class="scurve-canvas" role="img" aria-label="Planned, forecast and actual progress curve"></canvas>';
    main.appendChild(chartPanel);

    const dataTableWrap = document.createElement('div');
    dataTableWrap.className = 'panel';
    dataTableWrap.innerHTML = '<h3>Chart data table (accessible alternative)</h3><div id="chart-table" class="table-scroll"></div>';
    main.appendChild(dataTableWrap);

    renderProgramSCurve(activeProgram);

    const buildingsList = buildingsForProgram(activeProgram.id);
    const drill = document.createElement('div');
    drill.className = 'panel';
    drill.innerHTML = '<h2>Building / Contract Drill-Down</h2>';
    const table = document.createElement('table');
    table.className = 'data-table';
    table.innerHTML =
      '<thead><tr><th>Building / Contract</th><th>Budget</th><th>Planned %</th><th>Forecast %</th><th>Actual %</th><th>SPI</th><th>LPI</th></tr></thead>';
    const tbody = document.createElement('tbody');
    buildingsList.forEach((b) => {
      const bm = buildingMetrics(b);
      const bRow = document.createElement('tr');
      bRow.className = 'row-building';
      bRow.innerHTML =
        '<td><strong>' + esc(b.name) + '</strong></td><td>' + esc(fmtMoney(bm.budget)) + '</td><td>' + esc(fmtPct(bm.plannedPct)) +
        '</td><td>' + esc(fmtPct(bm.forecastPct)) + '</td><td>' + esc(fmtPct(bm.actualPct)) + '</td>' +
        '<td class="ratio-' + ratioStatus(bm.spi) + '">' + esc(formatRatio(bm.spi)) + '</td>' +
        '<td class="ratio-' + ratioStatus(bm.lpi) + '">' + esc(formatRatio(bm.lpi)) + '</td>';
      tbody.appendChild(bRow);
      contractsForBuilding(b.id).forEach((c) => {
        const cm = contractMetrics(c);
        const cRow = document.createElement('tr');
        cRow.className = 'row-contract';
        cRow.innerHTML =
          '<td class="indent">' + esc(c.name) + ' <span class="tag">' + esc(c.contractType) + '</span></td><td>' + esc(fmtMoney(cm.budget)) +
          '</td><td>' + esc(fmtPct(cm.plannedPct)) + '</td><td>' + esc(fmtPct(cm.forecastPct)) + '</td><td>' + esc(fmtPct(cm.actualPct)) + '</td>' +
          '<td class="ratio-' + ratioStatus(cm.spi) + '">' + esc(formatRatio(cm.spi)) + '</td>' +
          '<td class="ratio-' + ratioStatus(cm.lpi) + '">' + esc(formatRatio(cm.lpi)) + '</td>';
        tbody.appendChild(cRow);
      });
    });
    table.appendChild(tbody);
    const scrollWrap = document.createElement('div');
    scrollWrap.className = 'table-scroll';
    scrollWrap.appendChild(table);
    drill.appendChild(scrollWrap);
    main.appendChild(drill);

    const exceptions = [];
    state.ds.activities.forEach((a) => {
      const m = activityMetrics(a);
      if (!m.gateWeightCheck.valid && gatesForActivity(a.id).length) {
        exceptions.push(a.code + ' ' + a.name + ': gate weights total ' + m.gateWeightCheck.total.toFixed(1) + '% (must be 100%).');
      }
      if (m.spi != null && m.spi < 0.9) exceptions.push(a.code + ' ' + a.name + ': SPI ' + formatRatio(m.spi) + ' — behind plan.');
      if (m.lpi != null && m.lpi < 0.9) exceptions.push(a.code + ' ' + a.name + ': LPI ' + formatRatio(m.lpi) + ' — unfavorable productivity.');
    });
    if (exceptions.length) {
      const excPanel = document.createElement('div');
      excPanel.className = 'panel exceptions-panel';
      excPanel.innerHTML = '<h2>Attention Needed</h2>';
      const ul = document.createElement('ul');
      exceptions.forEach((e) => {
        const li = document.createElement('li');
        li.textContent = e;
        ul.appendChild(li);
      });
      excPanel.appendChild(ul);
      main.appendChild(excPanel);
    }
  }

  function renderProgramSCurve(program) {
    const acts = state.ds.activities.filter((a) => {
      const contract = state.ds.contracts.find((c) => c.id === a.contractId);
      const building = contract ? state.ds.buildings.find((b) => b.id === contract.buildingId) : null;
      return building && building.programId === program.id;
    });
    if (!acts.length) return;
    const starts = acts.map((a) => a.baselineStart).filter(Boolean).sort();
    const finishes = acts.map((a) => a.baselineFinish).filter(Boolean).sort();
    const fFinishes = acts.map((a) => a.forecastFinish).filter(Boolean).sort();
    if (!starts.length || !finishes.length) return;
    const overallStart = starts[0];
    const overallFinish = finishes[finishes.length - 1] > (fFinishes[fFinishes.length - 1] || '') ? finishes[finishes.length - 1] : fFinishes[fFinishes.length - 1];
    const boundaries = periodBoundaryDates(overallStart, overallFinish, state.ds.settings.reportingPeriod);

    function seriesFor(kind) {
      return boundaries.map((d) => {
        let sum = 0;
        acts.forEach((a) => {
          if (kind === 'planned') sum += a.budget * (progressPctAtDate(a.baselineStart, a.baselineFinish, a.baselineCurve, d) / 100);
          else if (kind === 'forecast') sum += a.budget * (activityForecastPct(a, d) / 100);
          else {
            const gates = gatesForActivity(a.id);
            const actPct = d <= asOfDate() ? activityActualPct(a, gates) : null;
            if (actPct != null && d <= asOfDate()) sum += a.budget * (actPct / 100);
          }
        });
        const totalBudget = acts.reduce((s, a) => s + a.budget, 0) || 1;
        return { date: d, y: (sum / totalBudget) * 100 };
      });
    }
    const plannedSeries = seriesFor('planned');
    const forecastSeries = seriesFor('forecast');
    const actualSeries = seriesFor('actual').filter((p) => p.date <= asOfDate());

    const series = [
      { key: 'planned', name: 'Planned', color: '#5b7fb0', points: plannedSeries.map((p) => ({ x: p.date, y: p.y, label: p.date })) },
      { key: 'forecast', name: 'Forecast', color: '#c98a2b', points: forecastSeries.map((p) => ({ x: p.date, y: p.y, label: p.date })) },
      { key: 'actual', name: 'Actual', color: '#2f9e5b', points: actualSeries.map((p) => ({ x: p.date, y: p.y, label: p.date })) },
    ];
    const canvas = document.getElementById('scurve-canvas');
    if (canvas) drawSCurve(canvas, series);
    const legend = document.getElementById('chart-legend');
    if (legend) legend.innerHTML = buildLegendHtml(series);
    const tableContainer = document.getElementById('chart-table');
    if (tableContainer) renderChartDataTable(tableContainer, series, boundaries);
  }

  // ---------- Program Structure ----------
  function renderStructure(main) {
    main.innerHTML = '<h1>Program Structure</h1>';

    const addProgramPanel = document.createElement('div');
    addProgramPanel.className = 'panel';
    addProgramPanel.innerHTML =
      '<h2>Add Program</h2><form id="add-program-form" class="inline-form">' +
      '<input name="name" placeholder="Program name" required>' +
      '<input name="description" placeholder="Description">' +
      '<button type="submit">Add Program</button></form>';
    main.appendChild(addProgramPanel);
    addProgramPanel.querySelector('#add-program-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const program = makeProgram({ name: fd.get('name'), description: fd.get('description') });
      state.ds.programs.push(program);
      audit('program', program.id, 'program-created', {}, program);
      persist().then(render);
    });

    state.ds.programs.forEach((program) => {
      const panel = document.createElement('div');
      panel.className = 'panel';
      panel.innerHTML = '<h2>' + esc(program.name) + '</h2><p class="muted">' + esc(program.description) + '</p>';

      const addBuildingForm = document.createElement('form');
      addBuildingForm.className = 'inline-form';
      addBuildingForm.innerHTML =
        '<input name="name" placeholder="Building name" required><input name="description" placeholder="Description"><button type="submit">Add Building</button>';
      addBuildingForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const b = makeBuilding({ programId: program.id, name: fd.get('name'), description: fd.get('description') });
        state.ds.buildings.push(b);
        audit('building', b.id, 'building-created', {}, b);
        persist().then(render);
      });
      panel.appendChild(addBuildingForm);

      buildingsForProgram(program.id).forEach((building) => {
        const bDiv = document.createElement('div');
        bDiv.className = 'nested-block';
        bDiv.innerHTML = '<h3>' + esc(building.name) + '</h3>';

        const addContractForm = document.createElement('form');
        addContractForm.className = 'inline-form contract-form';
        addContractForm.innerHTML =
          '<input name="name" placeholder="Contract name" required>' +
          '<input name="contractType" placeholder="Type/Discipline" value="General">' +
          '<input name="authorizedBudget" type="number" step="0.01" placeholder="Authorized budget">' +
          '<input name="authorizedHours" type="number" step="0.1" placeholder="Authorized hours">' +
          '<label>Baseline start<input name="baselineStart" type="date"></label>' +
          '<label>Baseline finish<input name="baselineFinish" type="date"></label>' +
          '<label>Forecast start<input name="forecastStart" type="date"></label>' +
          '<label>Forecast finish<input name="forecastFinish" type="date"></label>' +
          '<button type="submit">Add Contract</button>';
        addContractForm.addEventListener('submit', (e) => {
          e.preventDefault();
          const fd = new FormData(e.target);
          const c = makeContract({
            buildingId: building.id,
            name: fd.get('name'),
            contractType: fd.get('contractType') || 'General',
            authorizedBudget: fd.get('authorizedBudget'),
            authorizedHours: fd.get('authorizedHours'),
            baselineStart: fd.get('baselineStart'),
            baselineFinish: fd.get('baselineFinish'),
            forecastStart: fd.get('forecastStart'),
            forecastFinish: fd.get('forecastFinish'),
          });
          state.ds.contracts.push(c);
          audit('contract', c.id, 'contract-created', {}, c);
          persist().then(render);
        });
        bDiv.appendChild(addContractForm);

        const cTable = document.createElement('table');
        cTable.className = 'data-table';
        cTable.innerHTML = '<thead><tr><th>Contract</th><th>Type</th><th>Budget</th><th>Hours</th><th>Baseline</th><th>Forecast</th><th></th></tr></thead>';
        const cTbody = document.createElement('tbody');
        contractsForBuilding(building.id).forEach((c) => {
          const row = document.createElement('tr');
          row.innerHTML =
            '<td>' + esc(c.name) + '</td><td>' + esc(c.contractType) + '</td><td>' + esc(fmtMoney(c.authorizedBudget)) +
            '</td><td>' + esc(fmtHours(c.authorizedHours)) + '</td><td>' + esc(c.baselineStart) + ' → ' + esc(c.baselineFinish) +
            '</td><td>' + esc(c.forecastStart) + ' → ' + esc(c.forecastFinish) + '</td><td><button data-act="add-activity">+ Activity</button></td>';
          row.querySelector('[data-act="add-activity"]').addEventListener('click', () => {
            state.selection.contractId = c.id;
            state.tab = 'activities';
            render();
          });
          cTbody.appendChild(row);
        });
        cTable.appendChild(cTbody);
        const scroll = document.createElement('div');
        scroll.className = 'table-scroll';
        scroll.appendChild(cTable);
        bDiv.appendChild(scroll);
        panel.appendChild(bDiv);
      });
      main.appendChild(panel);
    });
  }

  // ---------- Activities grid ----------
  function renderActivities(main) {
    main.innerHTML = '<h1>Activities</h1>';

    const filterPanel = document.createElement('div');
    filterPanel.className = 'panel controls-row';
    filterPanel.innerHTML =
      '<label>Contract <select id="filter-contract"><option value="">All contracts</option></select></label>' +
      '<label>Search <input id="filter-search" placeholder="Code or name"></label>';
    main.appendChild(filterPanel);
    const contractSelect = filterPanel.querySelector('#filter-contract');
    state.ds.contracts.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.name;
      contractSelect.appendChild(opt);
    });
    if (state.selection.contractId) contractSelect.value = state.selection.contractId;

    const addPanel = document.createElement('div');
    addPanel.className = 'panel';
    addPanel.innerHTML =
      '<h2>Add Activity</h2><form id="add-activity-form" class="inline-form">' +
      '<label>Contract <select name="contractId" required></select></label>' +
      '<input name="code" placeholder="Activity code / WBS">' +
      '<input name="name" placeholder="Activity name" required>' +
      '<input name="budget" type="number" step="0.01" placeholder="Budget">' +
      '<input name="plannedHours" type="number" step="0.1" placeholder="Planned hours">' +
      '<label>Baseline start<input name="baselineStart" type="date"></label>' +
      '<label>Baseline finish<input name="baselineFinish" type="date"></label>' +
      '<label>Forecast start<input name="forecastStart" type="date"></label>' +
      '<label>Forecast finish<input name="forecastFinish" type="date"></label>' +
      '<label>Baseline curve <select name="baselineCurve"></select></label>' +
      '<label>Forecast curve <select name="forecastCurve"></select></label>' +
      '<button type="submit">Add Activity</button></form>';
    main.appendChild(addPanel);
    const contractSelect2 = addPanel.querySelector('select[name="contractId"]');
    state.ds.contracts.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.name;
      contractSelect2.appendChild(opt);
    });
    if (state.selection.contractId) contractSelect2.value = state.selection.contractId;
    ['baselineCurve', 'forecastCurve'].forEach((field) => {
      const sel = addPanel.querySelector('select[name="' + field + '"]');
      Object.values(CURVE_TYPES).forEach((ct) => {
        const opt = document.createElement('option');
        opt.value = ct;
        opt.textContent = CURVE_LABELS[ct];
        if (ct === CURVE_TYPES.S_CURVE) opt.selected = true;
        sel.appendChild(opt);
      });
    });
    addPanel.querySelector('#add-activity-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const a = makeActivity({
        contractId: fd.get('contractId'),
        code: fd.get('code'),
        name: fd.get('name'),
        budget: fd.get('budget'),
        plannedHours: fd.get('plannedHours'),
        baselineStart: fd.get('baselineStart'),
        baselineFinish: fd.get('baselineFinish'),
        forecastStart: fd.get('forecastStart'),
        forecastFinish: fd.get('forecastFinish'),
        baselineCurve: fd.get('baselineCurve'),
        forecastCurve: fd.get('forecastCurve'),
      });
      state.ds.activities.push(a);
      audit('activity', a.id, 'activity-created', {}, a);
      persist().then(render);
    });

    const gridPanel = document.createElement('div');
    gridPanel.className = 'panel';
    const table = document.createElement('table');
    table.className = 'data-table sticky-header';
    table.innerHTML =
      '<thead><tr><th>Code</th><th>Activity</th><th>Contract</th><th>Planned %</th><th>Forecast %</th><th>Actual %</th><th>Variance</th>' +
      '<th>Planned Hrs</th><th>Actual Hrs</th><th>SPI</th><th>LPI</th><th></th></tr></thead>';
    const tbody = document.createElement('tbody');
    let acts = state.ds.activities;
    table.appendChild(tbody);
    const scroll = document.createElement('div');
    scroll.className = 'table-scroll';
    scroll.appendChild(table);
    gridPanel.appendChild(scroll);
    main.appendChild(gridPanel);

    function paint() {
      const contractFilter = contractSelect.value;
      const search = (filterPanel.querySelector('#filter-search').value || '').toLowerCase();
      tbody.innerHTML = '';
      acts
        .filter((a) => !contractFilter || a.contractId === contractFilter)
        .filter((a) => !search || (a.code + ' ' + a.name).toLowerCase().includes(search))
        .forEach((a) => {
          const m = activityMetrics(a);
          const contract = state.ds.contracts.find((c) => c.id === a.contractId);
          const row = document.createElement('tr');
          row.innerHTML =
            '<td>' + esc(a.code) + '</td><td>' + esc(a.name) + '</td><td>' + esc(contract ? contract.name : '') + '</td>' +
            '<td>' + esc(fmtPct(m.plannedPct)) + '</td><td>' + esc(fmtPct(m.forecastPct)) + (a.forecastOverride ? ' <span class="tag tag-override">override</span>' : '') +
            '</td><td>' + esc(fmtPct(m.actualPct)) + (a.actualOverride ? ' <span class="tag tag-override">override</span>' : '') +
            '</td><td>' + esc(fmtPct(m.actualPct - m.plannedPct)) + '</td>' +
            '<td>' + esc(fmtHours(m.plannedHours)) + '</td><td>' + esc(fmtHours(m.actualHours)) + '</td>' +
            '<td class="ratio-' + ratioStatus(m.spi) + '">' + esc(formatRatio(m.spi)) + '</td>' +
            '<td class="ratio-' + ratioStatus(m.lpi) + '">' + esc(formatRatio(m.lpi)) + '</td>' +
            '<td><button data-open>Open</button></td>';
          row.querySelector('[data-open]').addEventListener('click', () => {
            state.selection.activityId = a.id;
            state.tab = 'activityDetail';
            render();
          });
          tbody.appendChild(row);
        });
    }
    paint();
    contractSelect.addEventListener('change', paint);
    filterPanel.querySelector('#filter-search').addEventListener('input', paint);
  }

  // ---------- Activity Detail / Gates ----------
  function renderActivityDetail(main) {
    const activity = state.ds.activities.find((a) => a.id === state.selection.activityId);
    if (!activity) {
      main.innerHTML = '<p>No activity selected. Return to <strong>Activities</strong>.</p>';
      return;
    }
    const gates = gatesForActivity(activity.id);
    const m = activityMetrics(activity);

    main.innerHTML = '';
    const back = document.createElement('button');
    back.textContent = '← Back to Activities';
    back.className = 'link-btn';
    back.addEventListener('click', () => {
      state.tab = 'activities';
      render();
    });
    main.appendChild(back);

    const header = document.createElement('div');
    header.className = 'panel';
    header.innerHTML =
      '<h1>' + esc(activity.code) + ' — ' + esc(activity.name) + '</h1>' +
      '<p class="muted">' + esc(activity.description) + '</p>';
    main.appendChild(header);

    function field(label, name, value, type) {
      return '<label>' + esc(label) + '<input name="' + name + '" type="' + (type || 'text') + '" value="' + esc(value == null ? '' : value) + '"></label>';
    }
    function selectField(label, name, value) {
      let opts = Object.values(CURVE_TYPES)
        .map((ct) => '<option value="' + ct + '"' + (ct === value ? ' selected' : '') + '>' + CURVE_LABELS[ct] + '</option>')
        .join('');
      return '<label>' + esc(label) + '<select name="' + name + '">' + opts + '</select></label>';
    }

    const editForm = document.createElement('form');
    editForm.className = 'panel form-grid';
    editForm.innerHTML =
      '<h2>Activity Details</h2>' +
      field('Name', 'name', activity.name) +
      field('Code / WBS', 'code', activity.code) +
      field('Description', 'description', activity.description) +
      field('Budget', 'budget', activity.budget, 'number') +
      field('Planned Hours', 'plannedHours', activity.plannedHours, 'number') +
      field('Baseline Start', 'baselineStart', activity.baselineStart, 'date') +
      field('Baseline Finish', 'baselineFinish', activity.baselineFinish, 'date') +
      field('Forecast Start', 'forecastStart', activity.forecastStart, 'date') +
      field('Forecast Finish', 'forecastFinish', activity.forecastFinish, 'date') +
      selectField('Baseline Curve', 'baselineCurve', activity.baselineCurve) +
      selectField('Forecast Curve', 'forecastCurve', activity.forecastCurve) +
      '<button type="submit">Save Activity</button>';
    main.appendChild(editForm);
    editForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const before = { ...activity };
      activity.name = fd.get('name');
      activity.code = fd.get('code');
      activity.description = fd.get('description');
      activity.budget = Number(fd.get('budget')) || 0;
      activity.plannedHours = Number(fd.get('plannedHours')) || 0;
      activity.baselineStart = fd.get('baselineStart');
      activity.baselineFinish = fd.get('baselineFinish');
      activity.forecastStart = fd.get('forecastStart');
      activity.forecastFinish = fd.get('forecastFinish');
      activity.baselineCurve = fd.get('baselineCurve');
      activity.forecastCurve = fd.get('forecastCurve');
      activity.updatedAt = nowIso();
      audit('activity', activity.id, 'activity-updated', before, activity);
      persist().then(render);
    });

    const kpiRow = document.createElement('div');
    kpiRow.className = 'kpi-row';
    kpiRow.appendChild(kpiCard('Planned %', fmtPct(m.plannedPct)));
    kpiRow.appendChild(kpiCard('Forecast %', fmtPct(m.forecastPct) + (activity.forecastOverride ? ' (override)' : ' (calc)')));
    kpiRow.appendChild(kpiCard('Actual %', fmtPct(m.actualPct) + (activity.actualOverride ? ' (override)' : ' (calc)')));
    kpiRow.appendChild(kpiCard('Calculated Actual (gates)', fmtPct(m.calcActualPct)));
    kpiRow.appendChild(kpiCard('Earned Hours', fmtHours(m.earnedHours)));
    kpiRow.appendChild(kpiCard('Actual Hours', fmtHours(m.actualHours)));
    kpiRow.appendChild(kpiCard('SPI', formatRatio(m.spi), ratioStatus(m.spi)));
    kpiRow.appendChild(kpiCard('LPI', formatRatio(m.lpi), ratioStatus(m.lpi)));
    main.appendChild(kpiRow);

    const fPanel = document.createElement('div');
    fPanel.className = 'panel';
    fPanel.innerHTML =
      '<h2>Forecast Override</h2>' +
      (activity.forecastOverride
        ? '<p>Current override: <strong>' + esc(activity.forecastOverride.pct) + '%</strong> — ' + esc(activity.forecastOverride.reason) +
          ' <span class="muted">(' + esc(activity.forecastOverride.by) + ', ' + esc(activity.forecastOverride.statusDate) + ')</span></p>' +
          '<button id="reset-forecast">Reset to Calculated</button>'
        : '<form id="forecast-override-form" class="inline-form">' +
          '<input name="pct" type="number" min="0" max="100" step="0.1" placeholder="Override %" required>' +
          '<input name="reason" placeholder="Reason (required)" required>' +
          '<button type="submit">Apply Override</button></form>');
    main.appendChild(fPanel);
    const fForm = fPanel.querySelector('#forecast-override-form');
    if (fForm) {
      fForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const before = { forecastOverride: activity.forecastOverride };
        activity.forecastOverride = { pct: clampPct(fd.get('pct')), reason: fd.get('reason'), statusDate: asOfDate(), by: admin(), at: nowIso() };
        audit('activity', activity.id, 'forecast-overridden', before, { forecastOverride: activity.forecastOverride }, fd.get('reason'));
        persist().then(render);
      });
    }
    const resetForecastBtn = fPanel.querySelector('#reset-forecast');
    if (resetForecastBtn) {
      resetForecastBtn.addEventListener('click', () => {
        const before = { forecastOverride: activity.forecastOverride };
        activity.forecastOverride = null;
        audit('activity', activity.id, 'forecast-reset', before, { forecastOverride: null });
        persist().then(render);
      });
    }

    const aPanel = document.createElement('div');
    aPanel.className = 'panel';
    aPanel.innerHTML =
      '<h2>Actual % Override</h2><p class="muted">Calculated actual from gates: ' + esc(fmtPct(m.calcActualPct)) + '</p>' +
      (activity.actualOverride
        ? '<p>Current override: <strong>' + esc(activity.actualOverride.pct) + '%</strong> — ' + esc(activity.actualOverride.reason) +
          ' <span class="muted">(' + esc(activity.actualOverride.by) + ', ' + esc(activity.actualOverride.statusDate) + ')</span></p>' +
          '<button id="reset-actual">Reset to Calculated</button>'
        : '<form id="actual-override-form" class="inline-form">' +
          '<input name="pct" type="number" min="0" max="100" step="0.1" placeholder="Override %" required>' +
          '<input name="reason" placeholder="Reason (required)" required>' +
          '<button type="submit">Apply Override</button></form>');
    main.appendChild(aPanel);
    const aForm = aPanel.querySelector('#actual-override-form');
    if (aForm) {
      aForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const before = { actualOverride: activity.actualOverride };
        activity.actualOverride = { pct: clampPct(fd.get('pct')), reason: fd.get('reason'), statusDate: asOfDate(), by: admin(), at: nowIso() };
        audit('activity', activity.id, 'actual-overridden', before, { actualOverride: activity.actualOverride }, fd.get('reason'));
        persist().then(render);
      });
    }
    const resetActualBtn = aPanel.querySelector('#reset-actual');
    if (resetActualBtn) {
      resetActualBtn.addEventListener('click', () => {
        const before = { actualOverride: activity.actualOverride };
        activity.actualOverride = null;
        audit('activity', activity.id, 'actual-reset', before, { actualOverride: null });
        persist().then(render);
      });
    }

    const gatesPanel = document.createElement('div');
    gatesPanel.className = 'panel';
    const weightCheck = validateGateWeights(gates);
    gatesPanel.innerHTML =
      '<h2>Rules of Credit / Gates</h2>' +
      '<p class="' + (weightCheck.valid ? 'muted' : 'warning-text') + '">Total weight: ' + esc(weightCheck.total.toFixed(1)) + '% ' +
      (weightCheck.valid ? '(valid)' : '(must total 100%, tolerance ' + GATE_WEIGHT_TOLERANCE + ')') + ' &nbsp; Live earned actual: <strong>' + esc(fmtPct(m.calcActualPct)) + '</strong></p>';
    main.appendChild(gatesPanel);

    const gTable = document.createElement('table');
    gTable.className = 'data-table';
    gTable.innerHTML = '<thead><tr><th>#</th><th>Gate name</th><th>Weight %</th><th>Completion %</th><th>Status date</th><th>Notes</th><th>Updated by</th><th></th></tr></thead>';
    const gTbody = document.createElement('tbody');
    gates.forEach((g, idx) => {
      const row = document.createElement('tr');
      row.innerHTML =
        '<td>' + (idx + 1) + '</td>' +
        '<td><input data-f="name" value="' + esc(g.name) + '"></td>' +
        '<td><input data-f="weightPct" type="number" min="0" max="100" step="0.1" value="' + esc(g.weightPct) + '"></td>' +
        '<td><input data-f="completionPct" type="number" min="0" max="100" step="0.1" value="' + esc(g.completionPct) + '"></td>' +
        '<td><input data-f="statusDate" type="date" value="' + esc(g.statusDate) + '"></td>' +
        '<td><input data-f="notes" value="' + esc(g.notes) + '"></td>' +
        '<td class="muted">' + esc(g.updatedBy) + '</td>' +
        '<td><button data-move-up>↑</button><button data-move-down>↓</button><button data-delete>Delete</button></td>';
      ['name', 'weightPct', 'completionPct', 'statusDate', 'notes'].forEach((f) => {
        row.querySelector('[data-f="' + f + '"]').addEventListener('change', (e) => {
          const before = { ...g };
          const val = f === 'weightPct' || f === 'completionPct' ? clampPct(e.target.value) : e.target.value;
          g[f] = val;
          g.updatedBy = admin();
          g.updatedAt = nowIso();
          audit('gate', g.id, 'gate-' + f + '-updated', before, { ...g });
          persist().then(render);
        });
      });
      row.querySelector('[data-delete]').addEventListener('click', () => {
        const before = { ...g };
        state.ds.gates = state.ds.gates.filter((x) => x.id !== g.id);
        audit('gate', g.id, 'gate-deleted', before, {});
        persist().then(render);
      });
      row.querySelector('[data-move-up]').addEventListener('click', () => {
        if (idx === 0) return;
        [gates[idx - 1].order, gates[idx].order] = [gates[idx].order, gates[idx - 1].order];
        audit('gate', g.id, 'gate-reordered', {}, {});
        persist().then(render);
      });
      row.querySelector('[data-move-down]').addEventListener('click', () => {
        if (idx === gates.length - 1) return;
        [gates[idx + 1].order, gates[idx].order] = [gates[idx].order, gates[idx + 1].order];
        audit('gate', g.id, 'gate-reordered', {}, {});
        persist().then(render);
      });
      gTbody.appendChild(row);
    });
    gTable.appendChild(gTbody);
    const gScroll = document.createElement('div');
    gScroll.className = 'table-scroll';
    gScroll.appendChild(gTable);
    gatesPanel.appendChild(gScroll);

    const addGateForm = document.createElement('form');
    addGateForm.className = 'inline-form';
    addGateForm.innerHTML =
      '<input name="name" placeholder="Gate name" required>' +
      '<input name="weightPct" type="number" min="0" max="100" step="0.1" placeholder="Weight %" required>' +
      '<input name="completionPct" type="number" min="0" max="100" step="0.1" placeholder="Completion %" value="0">' +
      '<button type="submit">Add Gate</button>';
    addGateForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const g = makeGate({
        activityId: activity.id,
        name: fd.get('name'),
        weightPct: fd.get('weightPct'),
        completionPct: fd.get('completionPct'),
        statusDate: asOfDate(),
        updatedBy: admin(),
        order: gates.length,
      });
      state.ds.gates.push(g);
      audit('gate', g.id, 'gate-added', {}, g);
      persist().then(render);
    });
    gatesPanel.appendChild(addGateForm);

    const auditPanel = document.createElement('div');
    auditPanel.className = 'panel';
    auditPanel.innerHTML = '<h2>Audit History</h2>';
    const events = state.ds.auditEvents
      .filter((ev) => (ev.entityType === 'activity' && ev.entityId === activity.id) || (ev.entityType === 'gate' && gates.some((g) => g.id === ev.entityId)))
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
      .slice(0, 50);
    const aTable = document.createElement('table');
    aTable.className = 'data-table';
    aTable.innerHTML = '<thead><tr><th>Timestamp</th><th>Event</th><th>By</th><th>Reason</th></tr></thead>';
    const aTbody = document.createElement('tbody');
    events.forEach((ev) => {
      const row = document.createElement('tr');
      row.innerHTML = '<td>' + esc(ev.timestamp) + '</td><td>' + esc(ev.eventType) + '</td><td>' + esc(ev.performedBy) + '</td><td>' + esc(ev.reason) + '</td>';
      aTbody.appendChild(row);
    });
    aTable.appendChild(aTbody);
    const aScroll = document.createElement('div');
    aScroll.className = 'table-scroll';
    aScroll.appendChild(aTable);
    auditPanel.appendChild(aScroll);
    main.appendChild(auditPanel);
  }

  // ---------- Hours ----------
  function renderHours(main) {
    main.innerHTML = '<h1>Actual Hours</h1>';
    const open = getOpenPeriod(state.ds.periods);
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML =
      '<h2>Enter Actual Hours</h2>' +
      (open ? '<p class="muted">Current open period: ' + esc(open.label) + ' (' + esc(open.startDate) + ' to ' + esc(open.endDate) + ')</p>' : '<p class="warning-text">No open period. Go to Reporting Periods.</p>') +
      '<form id="hours-form" class="inline-form">' +
      '<label>Activity <select name="activityId" required></select></label>' +
      '<label>Date <input name="date" type="date" required value="' + esc(asOfDate()) + '"></label>' +
      '<input name="hours" type="number" step="0.1" min="0" placeholder="Hours" required>' +
      '<input name="notes" placeholder="Notes">' +
      '<button type="submit">Add Record</button></form>';
    main.appendChild(panel);
    const sel = panel.querySelector('select[name="activityId"]');
    state.ds.activities.forEach((a) => {
      const opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = a.code + ' — ' + a.name;
      sel.appendChild(opt);
    });
    panel.querySelector('#hours-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const dateVal = fd.get('date');
      if (open && !isDateInPeriod(dateVal, open)) {
        alert('Date is outside the currently open reporting period (' + open.startDate + ' to ' + open.endDate + '). Actual-hour entries must fall in the open period.');
        return;
      }
      const rec = makeActualHourRecord({
        activityId: fd.get('activityId'),
        date: dateVal,
        hours: fd.get('hours'),
        notes: fd.get('notes'),
        enteredBy: admin(),
        periodId: open ? open.id : null,
      });
      state.ds.actualHours.push(rec);
      audit('actualHours', rec.id, 'actual-hours-entered', {}, rec);
      persist().then(render);
    });

    const historyPanel = document.createElement('div');
    historyPanel.className = 'panel';
    historyPanel.innerHTML = '<h2>Actual Hour Records</h2>';
    const table = document.createElement('table');
    table.className = 'data-table sticky-header';
    table.innerHTML = '<thead><tr><th>Date</th><th>Activity</th><th>Hours</th><th>Notes</th><th>Entered By</th><th>Period</th></tr></thead>';
    const tbody = document.createElement('tbody');
    state.ds.actualHours
      .slice()
      .sort((a, b) => (a.date < b.date ? 1 : -1))
      .forEach((r) => {
        const a = state.ds.activities.find((x) => x.id === r.activityId);
        const period = state.ds.periods.find((p) => p.id === r.periodId);
        const row = document.createElement('tr');
        row.innerHTML =
          '<td>' + esc(r.date) + '</td><td>' + esc(a ? a.code + ' ' + a.name : '') + '</td><td>' + esc(fmtHours(r.hours)) + '</td>' +
          '<td>' + esc(r.notes) + '</td><td>' + esc(r.enteredBy) + '</td><td>' + esc(period ? period.label + ' (' + period.status + ')' : '—') + '</td>';
        tbody.appendChild(row);
      });
    table.appendChild(tbody);
    const scroll = document.createElement('div');
    scroll.className = 'table-scroll';
    scroll.appendChild(table);
    historyPanel.appendChild(scroll);
    main.appendChild(historyPanel);
  }

  // ---------- Reporting Periods ----------
  function renderPeriods(main) {
    main.innerHTML = '<h1>Reporting Periods</h1>';
    const open = getOpenPeriod(state.ds.periods);

    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML = open
      ? '<h2>Open Period</h2><p><strong>' + esc(open.label) + '</strong> (' + esc(open.startDate) + ' to ' + esc(open.endDate) + ')</p><button id="close-period-btn">Close Period &amp; Advance</button>'
      : '<h2>No Open Period</h2><button id="start-period-btn">Start Period</button>';
    main.appendChild(panel);

    const startBtn = panel.querySelector('#start-period-btn');
    if (startBtn) {
      startBtn.addEventListener('click', () => {
        ensureOpenPeriod();
        persist().then(render);
      });
    }
    const closeBtn = panel.querySelector('#close-period-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        const program = state.ds.programs[0];
        const kpis = program ? programMetrics(program) : {};
        const rollups = {
          programs: state.ds.programs.map((p) => ({ id: p.id, metrics: programMetrics(p) })),
          buildings: state.ds.buildings.map((b) => ({ id: b.id, metrics: buildingMetrics(b) })),
          contracts: state.ds.contracts.map((c) => ({ id: c.id, metrics: contractMetrics(c) })),
          activities: state.ds.activities.map((a) => ({ id: a.id, metrics: activityMetrics(a) })),
        };
        closePeriodAndAdvance(state.ds.periods, state.ds.snapshots, state.ds.auditEvents, {
          kpis, rollups, performedBy: admin(), type: state.ds.settings.reportingPeriod,
        });
        persist().then(render);
      });
    }

    const closedPanel = document.createElement('div');
    closedPanel.className = 'panel';
    closedPanel.innerHTML = '<h2>Closed Periods</h2>';
    const table = document.createElement('table');
    table.className = 'data-table';
    table.innerHTML = '<thead><tr><th>Period</th><th>Dates</th><th>Status</th><th>Closed By</th><th>Closed At</th><th></th></tr></thead>';
    const tbody = document.createElement('tbody');
    state.ds.periods
      .filter((p) => p.status === PERIOD_STATUS.CLOSED)
      .sort((a, b) => (a.startDate < b.startDate ? 1 : -1))
      .forEach((p) => {
        const row = document.createElement('tr');
        row.innerHTML =
          '<td>' + esc(p.label) + '</td><td>' + esc(p.startDate) + ' → ' + esc(p.endDate) + '</td><td>' + esc(p.status) +
          '</td><td>' + esc(p.closedBy) + '</td><td>' + esc(p.closedAt) + '</td><td><button data-reopen>Reopen</button></td>';
        row.querySelector('[data-reopen]').addEventListener('click', () => {
          const reason = prompt('Enter a mandatory reason to reopen "' + p.label + '":');
          if (!reason || !reason.trim()) {
            alert('Reopen cancelled — a reason is required.');
            return;
          }
          try {
            reopenPeriod(state.ds.periods, state.ds.auditEvents, p.id, reason, admin());
            persist().then(render);
          } catch (err) {
            alert(err.message);
          }
        });
        tbody.appendChild(row);
      });
    table.appendChild(tbody);
    closedPanel.appendChild(table);
    main.appendChild(closedPanel);

    const snapPanel = document.createElement('div');
    snapPanel.className = 'panel';
    snapPanel.innerHTML = '<h2>Snapshots</h2>';
    const sTable = document.createElement('table');
    sTable.className = 'data-table';
    sTable.innerHTML = '<thead><tr><th>Snapshot</th><th>Planned Value</th><th>Earned Value</th><th>SPI (cum)</th><th>Earned Hrs</th><th>Actual Hrs</th><th>LPI (cum)</th><th>By</th><th>At</th></tr></thead>';
    const sTbody = document.createElement('tbody');
    state.ds.snapshots
      .slice()
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
      .forEach((s) => {
        const period = state.ds.periods.find((p) => p.id === s.periodId);
        const k = s.kpis || {};
        const row = document.createElement('tr');
        row.innerHTML =
          '<td>' + esc(period ? period.label : s.periodId) + '</td><td>' + esc(fmtMoney(k.plannedValue)) + '</td><td>' + esc(fmtMoney(k.earnedValue)) +
          '</td><td class="ratio-' + ratioStatus(k.spi) + '">' + esc(formatRatio(k.spi)) + '</td><td>' + esc(fmtHours(k.earnedHours)) +
          '</td><td>' + esc(fmtHours(k.actualHours)) + '</td><td class="ratio-' + ratioStatus(k.lpi) + '">' + esc(formatRatio(k.lpi)) +
          '</td><td>' + esc(s.performedBy) + '</td><td>' + esc(s.timestamp) + '</td>';
        sTbody.appendChild(row);
      });
    sTable.appendChild(sTbody);
    snapPanel.appendChild(sTable);
    main.appendChild(snapPanel);
  }

  // ---------- Settings / Data Manager ----------
  function renderSettings(main) {
    main.innerHTML = '<h1>Settings / Data Manager</h1>';

    const settingsPanel = document.createElement('div');
    settingsPanel.className = 'panel';
    settingsPanel.innerHTML =
      '<h2>Global Settings</h2><form id="settings-form" class="form-grid">' +
      '<label>Administrator name<input name="adminName" value="' + esc(state.ds.settings.adminName) + '"></label>' +
      '<label>Reporting currency (ISO code)<input name="reportingCurrency" value="' + esc(state.ds.settings.reportingCurrency) + '" maxlength="3"></label>' +
      '<label>Locale<input name="locale" value="' + esc(state.ds.settings.locale) + '"></label>' +
      '<label>Time zone<input name="timeZone" value="' + esc(state.ds.settings.timeZone) + '"></label>' +
      '<label>Default reporting period<select name="reportingPeriod">' +
      '<option value="weekly"' + (state.ds.settings.reportingPeriod === 'weekly' ? ' selected' : '') + '>Weekly</option>' +
      '<option value="monthly"' + (state.ds.settings.reportingPeriod === 'monthly' ? ' selected' : '') + '>Monthly</option></select></label>' +
      '<button type="submit">Save Settings</button></form>';
    main.appendChild(settingsPanel);
    settingsPanel.querySelector('#settings-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const before = { ...state.ds.settings };
      state.ds.settings.adminName = fd.get('adminName') || 'Admin';
      state.ds.settings.reportingCurrency = (fd.get('reportingCurrency') || 'USD').toUpperCase();
      state.ds.settings.locale = fd.get('locale') || 'en-US';
      state.ds.settings.timeZone = fd.get('timeZone') || 'America/New_York';
      state.ds.settings.reportingPeriod = fd.get('reportingPeriod');
      audit('settings', 'global', 'settings-updated', before, { ...state.ds.settings });
      persist().then(render);
    });

    const dataPanel = document.createElement('div');
    dataPanel.className = 'panel';
    dataPanel.innerHTML =
      '<h2>JSON Import / Export</h2>' +
      '<p class="muted">JSON export/import is the authoritative portable backup and data-transfer method for this tool.</p>' +
      '<button id="export-btn">Export JSON Backup</button> ' +
      '<label class="file-label">Import JSON<input type="file" id="import-file" accept="application/json"></label> ' +
      '<button id="load-sample-btn">Load Sample Data</button> ' +
      '<button id="reset-btn" class="danger-btn">Reset All Data</button>' +
      '<div id="import-status" class="muted"></div>';
    main.appendChild(dataPanel);

    dataPanel.querySelector('#export-btn').addEventListener('click', () => {
      exportDatasetToFile(state.ds, 'contract-progress-tracker');
    });
    dataPanel.querySelector('#import-file').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (!confirm('Importing will replace all current data. Export a backup first if you have not already. Continue?')) {
        e.target.value = '';
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const result = parseImportedJson(reader.result);
        const statusEl = dataPanel.querySelector('#import-status');
        if (!result.valid) {
          statusEl.textContent = 'Import failed: ' + result.errors.join(' ');
          statusEl.className = 'warning-text';
          return;
        }
        state.ds = result.dataset;
        audit('dataset', 'main', 'dataset-imported', {}, {});
        persist().then(() => {
          statusEl.textContent = 'Import successful.';
          statusEl.className = 'muted';
          render();
        });
      };
      reader.readAsText(file);
    });
    dataPanel.querySelector('#load-sample-btn').addEventListener('click', () => {
      if (!confirm('This will replace current data with sample data. Export a backup first if needed. Continue?')) return;
      state.ds = buildSampleDataset();
      state.ds.settings.adminName = state.ds.settings.adminName || 'Kevin';
      persist().then(render);
    });
    dataPanel.querySelector('#reset-btn').addEventListener('click', () => {
      if (!confirm('This permanently clears all data (after exporting a backup is recommended). Continue?')) return;
      import('./schema.js').then(({ emptyDataset }) => {
        state.ds = emptyDataset();
        persist().then(render);
      });
    });

    const aboutPanel = document.createElement('div');
    aboutPanel.className = 'panel';
    aboutPanel.innerHTML =
      '<h2>About</h2><p class="muted">Single-user local administrator mode. Storage: IndexedDB (with localStorage fallback). ' +
      'A future backend (e.g. Supabase/Postgres) may add authentication, multi-user collaboration, roles, files, and centralized audit control.</p>';
    main.appendChild(aboutPanel);
  }

  render();
  return { getState: () => state, render };
}
