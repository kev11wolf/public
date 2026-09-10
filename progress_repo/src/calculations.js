// calculations.js — Curves, progress, earned value, SPI/LPI, rollups
import { CURVE_TYPES, clampPct } from './schema.js';

// ---- Curve shape functions ----
// Each function takes fraction of time elapsed (0..1) and returns cumulative
// fraction of progress complete (0..1). All curves are monotonic 0->1.

function linearCurve(t) {
  return t;
}

// Standard symmetric S-curve using a smoothstep-like cosine ease
function sCurve(t) {
  return (1 - Math.cos(Math.PI * t)) / 2;
}

// Front-loaded: fast early progress, tapering — use sqrt shape
function frontLoadedCurve(t) {
  return Math.sqrt(t);
}

// Back-loaded: slow early progress, accelerating — use squared shape
function backLoadedCurve(t) {
  return t * t;
}

const CURVE_FN = {
  [CURVE_TYPES.LINEAR]: linearCurve,
  [CURVE_TYPES.S_CURVE]: sCurve,
  [CURVE_TYPES.FRONT_LOADED]: frontLoadedCurve,
  [CURVE_TYPES.BACK_LOADED]: backLoadedCurve,
};

export function curveFraction(curveType, t) {
  const fn = CURVE_FN[curveType] || sCurve;
  const clamped = Math.min(1, Math.max(0, t));
  return fn(clamped);
}

// Compute cumulative % complete (0..100) at a given asOfDate, based on
// start/finish dates and a curve type. Returns 0 before start, 100 after finish.
export function progressPctAtDate(startDate, finishDate, curveType, asOfDate) {
  if (!startDate || !finishDate) return 0;
  const start = new Date(startDate + 'T00:00:00');
  const finish = new Date(finishDate + 'T23:59:59');
  const asOf = new Date(asOfDate + 'T12:00:00');
  const totalMs = finish - start;
  if (totalMs <= 0) return asOf >= start ? 100 : 0;
  if (asOf <= start) return 0;
  if (asOf >= finish) return 100;
  const t = (asOf - start) / totalMs;
  return clampPct(curveFraction(curveType, t) * 100);
}

// Generate a time-phased series of {date, cumulativePct} at each period boundary
// between start and finish (inclusive), using the given curve.
export function timePhasedSeries(startDate, finishDate, curveType, periodDates) {
  return periodDates.map((d) => ({
    date: d,
    cumulativePct: progressPctAtDate(startDate, finishDate, curveType, d),
  }));
}

// ---- Gate / activity earned progress ----

export function gateEarnedCredit(gate) {
  const weight = Number(gate.weightPct) || 0;
  const completion = Number(gate.completionPct) || 0;
  return weight * (completion / 100);
}

// Activity earned actual % = sum(gate weight * completion/100), unless overridden
export function activityCalculatedActualPct(gates) {
  const sum = gates.reduce((acc, g) => acc + gateEarnedCredit(g), 0);
  return clampPct(sum);
}

export function activityActualPct(activity, gates) {
  if (activity.actualOverride && activity.actualOverride.pct != null) {
    return clampPct(activity.actualOverride.pct);
  }
  return activityCalculatedActualPct(gates);
}

export function activityForecastPct(activity, asOfDate) {
  if (activity.forecastOverride && activity.forecastOverride.pct != null) {
    return clampPct(activity.forecastOverride.pct);
  }
  return progressPctAtDate(activity.forecastStart, activity.forecastFinish, activity.forecastCurve, asOfDate);
}

export function activityPlannedPct(activity, asOfDate) {
  return progressPctAtDate(activity.baselineStart, activity.baselineFinish, activity.baselineCurve, asOfDate);
}

// ---- Earned / planned / actual value & hours ----

export function plannedValue(activity, asOfDate) {
  return activity.budget * (activityPlannedPct(activity, asOfDate) / 100);
}

export function forecastValue(activity, asOfDate) {
  return activity.budget * (activityForecastPct(activity, asOfDate) / 100);
}

export function earnedValue(activity, gates) {
  return activity.budget * (activityActualPct(activity, gates) / 100);
}

export function earnedHours(activity, gates) {
  return activity.plannedHours * (activityActualPct(activity, gates) / 100);
}

export function sumActualHours(records) {
  return records.reduce((acc, r) => acc + (Number(r.hours) || 0), 0);
}

// ---- SPI / LPI ----
// Never average ratios; always sum numerator & denominator first, then divide.

export function ratioOrDash(numerator, denominator) {
  if (!denominator || Math.abs(denominator) < 1e-9) return null; // caller renders as "—"
  return numerator / denominator;
}

export function computeSPI(totalEarnedValue, totalPlannedValue) {
  return ratioOrDash(totalEarnedValue, totalPlannedValue);
}

export function computeLPI(totalEarnedHours, totalActualHours) {
  return ratioOrDash(totalEarnedHours, totalActualHours);
}

export function formatRatio(r) {
  return r == null ? '—' : r.toFixed(2);
}

export function ratioStatus(r) {
  // returns 'good' | 'warn' | 'bad' | 'neutral'
  if (r == null) return 'neutral';
  if (r >= 1.0) return 'good';
  if (r >= 0.9) return 'warn';
  return 'bad';
}

// ---- Rollup aggregation helper ----
// Aggregates an array of { plannedValue, earnedValue, earnedHours, actualHours }
// into totals, then derives SPI/LPI from the totals (never averages ratios).
export function rollupTotals(items) {
  const totals = items.reduce(
    (acc, it) => {
      acc.plannedValue += it.plannedValue || 0;
      acc.forecastValue += it.forecastValue || 0;
      acc.earnedValue += it.earnedValue || 0;
      acc.earnedHours += it.earnedHours || 0;
      acc.actualHours += it.actualHours || 0;
      acc.budget += it.budget || 0;
      acc.plannedHours += it.plannedHours || 0;
      return acc;
    },
    { plannedValue: 0, forecastValue: 0, earnedValue: 0, earnedHours: 0, actualHours: 0, budget: 0, plannedHours: 0 }
  );
  totals.spi = computeSPI(totals.earnedValue, totals.plannedValue);
  totals.lpi = computeLPI(totals.earnedHours, totals.actualHours);
  totals.actualPct = totals.budget ? clampPct((totals.earnedValue / totals.budget) * 100) : 0;
  totals.plannedPct = totals.budget ? clampPct((totals.plannedValue / totals.budget) * 100) : 0;
  totals.forecastPct = totals.budget ? clampPct((totals.forecastValue / totals.budget) * 100) : 0;
  return totals;
}
