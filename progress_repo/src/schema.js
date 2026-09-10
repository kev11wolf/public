// schema.js — Data model, constants, defaults, and validation helpers
// Contract Progress Tracker — schemaVersion 2

export const SCHEMA_VERSION = 2;

export const CURVE_TYPES = {
  LINEAR: 'linear',
  S_CURVE: 's-curve',
  FRONT_LOADED: 'front-loaded',
  BACK_LOADED: 'back-loaded',
};

export const CURVE_LABELS = {
  [CURVE_TYPES.LINEAR]: 'Linear',
  [CURVE_TYPES.S_CURVE]: 'Standard S-Curve',
  [CURVE_TYPES.FRONT_LOADED]: 'Front-Loaded',
  [CURVE_TYPES.BACK_LOADED]: 'Back-Loaded',
};

export const REPORTING_PERIODS = {
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
};

export const PERIOD_STATUS = {
  OPEN: 'open',
  CLOSED: 'closed',
};

export const GATE_WEIGHT_TOLERANCE = 0.05; // percentage points tolerance for 100% validation

export function uuid() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  // RFC4122-ish fallback
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function nowIso() {
  return new Date().toISOString();
}

export function defaultSettings() {
  return {
    schemaVersion: SCHEMA_VERSION,
    settings: {
      adminName: 'Kevin',
      reportingCurrency: 'USD',
      locale: 'en-US',
      timeZone: 'America/New_York',
      reportingPeriod: REPORTING_PERIODS.WEEKLY,
      statusDate: new Date().toISOString().slice(0, 10),
    },
  };
}

export function emptyDataset() {
  const base = defaultSettings();
  return {
    schemaVersion: base.schemaVersion,
    settings: base.settings,
    programs: [],
    buildings: [],
    contracts: [],
    activities: [],
    gates: [],
    actualHours: [],
    auditEvents: [],
    periods: [],
    snapshots: [],
  };
}

export function makeProgram({ name, description = '' } = {}) {
  return {
    id: uuid(),
    name: name || 'New Program',
    description,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
}

export function makeBuilding({ programId, name, description = '' } = {}) {
  return {
    id: uuid(),
    programId,
    name: name || 'New Building',
    description,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
}

export function makeContract({
  buildingId,
  name,
  contractType = 'General',
  authorizedBudget = 0,
  authorizedHours = 0,
  baselineStart = '',
  baselineFinish = '',
  forecastStart = '',
  forecastFinish = '',
  status = 'Active',
} = {}) {
  return {
    id: uuid(),
    buildingId,
    name: name || 'New Contract',
    contractType,
    authorizedBudget: Number(authorizedBudget) || 0,
    authorizedHours: Number(authorizedHours) || 0,
    baselineStart,
    baselineFinish,
    forecastStart,
    forecastFinish,
    status,
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
}

export function makeActivity({
  contractId,
  code = '',
  name,
  description = '',
  budget = 0,
  plannedHours = 0,
  baselineStart = '',
  baselineFinish = '',
  forecastStart = '',
  forecastFinish = '',
  baselineCurve = CURVE_TYPES.S_CURVE,
  forecastCurve = CURVE_TYPES.S_CURVE,
} = {}) {
  return {
    id: uuid(),
    contractId,
    code,
    name: name || 'New Activity',
    description,
    budget: Number(budget) || 0,
    plannedHours: Number(plannedHours) || 0,
    baselineStart,
    baselineFinish,
    forecastStart,
    forecastFinish,
    baselineCurve,
    forecastCurve,
    forecastOverride: null, // { pct, reason, statusDate, by, at }
    actualOverride: null, // { pct, reason, statusDate, by, at }
    createdAt: nowIso(),
    updatedAt: nowIso(),
  };
}

export function makeGate({
  activityId,
  name,
  weightPct = 0,
  completionPct = 0,
  statusDate = '',
  notes = '',
  updatedBy = '',
  order = 0,
} = {}) {
  return {
    id: uuid(),
    activityId,
    name: name || 'New Gate',
    weightPct: Number(weightPct) || 0,
    completionPct: Number(completionPct) || 0,
    statusDate: statusDate || new Date().toISOString().slice(0, 10),
    notes,
    updatedBy,
    updatedAt: nowIso(),
    order,
  };
}

export function makeActualHourRecord({ activityId, date, hours, notes = '', enteredBy = '', periodId = null } = {}) {
  return {
    id: uuid(),
    activityId,
    date,
    hours: Number(hours) || 0,
    notes,
    enteredBy,
    enteredAt: nowIso(),
    periodId,
  };
}

export function makeAuditEvent({
  entityType,
  entityId,
  eventType,
  before = {},
  after = {},
  reason = '',
  periodId = null,
  performedBy = '',
} = {}) {
  return {
    id: uuid(),
    entityType,
    entityId,
    eventType,
    before,
    after,
    reason,
    periodId,
    performedBy,
    timestamp: nowIso(),
  };
}

export function makePeriod({ type, startDate, endDate, label, status = PERIOD_STATUS.OPEN } = {}) {
  return {
    id: uuid(),
    type, // weekly | monthly
    startDate, // ISO date, inclusive local start
    endDate, // ISO date, inclusive local end
    label,
    status,
    createdAt: nowIso(),
    closedAt: null,
    closedBy: null,
    reopenedHistory: [], // [{ reason, by, at }]
  };
}

export function makeSnapshot({ periodId, kpis, rollups, performedBy }) {
  return {
    id: uuid(),
    periodId,
    kpis, // { plannedValue, earnedValue, earnedHours, actualHours, periodSPI, cumulativeSPI, periodLPI, cumulativeLPI }
    rollups, // { program: {...}, buildings: [...], contracts: [...], activities: [...] }
    timestamp: nowIso(),
    performedBy,
  };
}

// Validate gate weights sum to ~100% (tolerance in percentage points)
export function validateGateWeights(gates) {
  const total = gates.reduce((sum, g) => sum + (Number(g.weightPct) || 0), 0);
  const diff = Math.abs(total - 100);
  return { valid: diff <= GATE_WEIGHT_TOLERANCE || gates.length === 0, total, diff };
}

export function clampPct(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

// Basic dataset shape validation for import
export function validateDataset(obj) {
  const errors = [];
  if (!obj || typeof obj !== 'object') {
    errors.push('File is not a valid JSON object.');
    return { valid: false, errors };
  }
  if (typeof obj.schemaVersion !== 'number') errors.push('Missing schemaVersion.');
  const requiredArrays = ['programs', 'buildings', 'contracts', 'activities', 'gates', 'actualHours', 'auditEvents', 'periods', 'snapshots'];
  requiredArrays.forEach((k) => {
    if (!Array.isArray(obj[k])) errors.push('Missing or invalid array: ' + k);
  });
  if (!obj.settings || typeof obj.settings !== 'object') errors.push('Missing settings object.');
  return { valid: errors.length === 0, errors };
}
