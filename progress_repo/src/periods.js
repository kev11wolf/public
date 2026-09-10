// periods.js — Reporting period bucketing, open/close lifecycle, snapshots
import { makePeriod, makeSnapshot, makeAuditEvent, PERIOD_STATUS, REPORTING_PERIODS, nowIso } from './schema.js';

function parseDate(iso) {
  return new Date(iso + 'T00:00:00');
}

function toIso(date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

// Weekly period: Sunday 12:01 AM through Saturday 11:59 PM (local project time)
export function weeklyPeriodFor(dateIso) {
  const d = parseDate(dateIso);
  const dow = d.getDay(); // 0 = Sunday
  const start = addDays(d, -dow);
  const end = addDays(start, 6);
  return {
    startDate: toIso(start),
    endDate: toIso(end),
    label: 'Week of ' + toIso(start),
  };
}

// Monthly period: 1st 12:01 AM through last day 11:59 PM
export function monthlyPeriodFor(dateIso) {
  const d = parseDate(dateIso);
  const start = new Date(d.getFullYear(), d.getMonth(), 1);
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return {
    startDate: toIso(start),
    endDate: toIso(end),
    label: start.toLocaleString('en-US', { month: 'long', year: 'numeric' }),
  };
}

export function periodBoundsFor(type, dateIso) {
  return type === REPORTING_PERIODS.MONTHLY ? monthlyPeriodFor(dateIso) : weeklyPeriodFor(dateIso);
}

export function periodBoundaryDates(startIso, finishIso, type) {
  if (!startIso || !finishIso) return [];
  const dates = [];
  let cursor = periodBoundsFor(type, startIso);
  let guard = 0;
  while (cursor.endDate <= finishIso && guard < 500) {
    dates.push(cursor.endDate);
    const next = addDays(parseDate(cursor.endDate), 1);
    cursor = periodBoundsFor(type, toIso(next));
    guard++;
  }
  if (dates.length === 0 || dates[dates.length - 1] < finishIso) dates.push(finishIso);
  return dates;
}

export function getOpenPeriod(periods) {
  return periods.find((p) => p.status === PERIOD_STATUS.OPEN) || null;
}

export function getOrCreateOpenPeriod(periods, type, statusDate) {
  let open = getOpenPeriod(periods);
  if (open) return open;
  const bounds = periodBoundsFor(type, statusDate);
  const period = makePeriod({ type, startDate: bounds.startDate, endDate: bounds.endDate, label: bounds.label, status: PERIOD_STATUS.OPEN });
  periods.push(period);
  return period;
}

export function closePeriodAndAdvance(periods, snapshots, auditEvents, { kpis, rollups, performedBy, type }) {
  const open = getOpenPeriod(periods);
  if (!open) throw new Error('No open period to close.');
  open.status = PERIOD_STATUS.CLOSED;
  open.closedAt = nowIso();
  open.closedBy = performedBy;

  const snapshot = makeSnapshot({ periodId: open.id, kpis, rollups, performedBy });
  snapshots.push(snapshot);

  const closeEvent = makeAuditEvent({
    entityType: 'period',
    entityId: open.id,
    eventType: 'period-closed',
    before: { status: PERIOD_STATUS.OPEN },
    after: { status: PERIOD_STATUS.CLOSED },
    periodId: open.id,
    performedBy,
  });
  auditEvents.push(closeEvent);

  const nextDayIso = toIso(addDays(parseDate(open.endDate), 1));
  const bounds = periodBoundsFor(type, nextDayIso);
  const newPeriod = makePeriod({ type, startDate: bounds.startDate, endDate: bounds.endDate, label: bounds.label, status: PERIOD_STATUS.OPEN });
  periods.push(newPeriod);

  return { closedPeriod: open, snapshot, newPeriod, auditEvents: [closeEvent] };
}

export function reopenPeriod(periods, auditEvents, periodId, reason, performedBy) {
  const period = periods.find((p) => p.id === periodId);
  if (!period) throw new Error('Period not found.');
  if (!reason || !reason.trim()) throw new Error('A reason is required to reopen a period.');
  const before = { status: period.status };
  period.status = PERIOD_STATUS.OPEN;
  period.reopenedHistory = period.reopenedHistory || [];
  period.reopenedHistory.push({ reason, by: performedBy, at: nowIso() });

  const event = makeAuditEvent({
    entityType: 'period',
    entityId: period.id,
    eventType: 'period-reopened',
    before,
    after: { status: PERIOD_STATUS.OPEN },
    reason,
    periodId: period.id,
    performedBy,
  });
  auditEvents.push(event);
  return { period, event };
}

export function isDateInPeriod(dateIso, period) {
  return dateIso >= period.startDate && dateIso <= period.endDate;
}

export function findPeriodForDate(periods, dateIso) {
  return periods.find((p) => isDateInPeriod(dateIso, p)) || null;
}
