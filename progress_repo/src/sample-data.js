// sample-data.js — Generates a realistic sample dataset for demo and testing
import {
  emptyDataset,
  makeProgram,
  makeBuilding,
  makeContract,
  makeActivity,
  makeGate,
  makeActualHourRecord,
  CURVE_TYPES,
} from './schema.js';
import { getOrCreateOpenPeriod } from './periods.js';

function isoDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function isoDaysFromNow(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export function buildSampleDataset() {
  const ds = emptyDataset();
  const admin = ds.settings.adminName || 'Kevin';

  const program = makeProgram({ name: 'Riverside Life-Sciences Campus', description: 'Multi-building biomanufacturing campus program.' });
  ds.programs.push(program);

  const buildingA = makeBuilding({ programId: program.id, name: 'Building A - Process', description: 'Core process manufacturing building.' });
  const buildingB = makeBuilding({ programId: program.id, name: 'Building B - Utilities', description: 'Central utility plant.' });
  ds.buildings.push(buildingA, buildingB);

  const contract1 = makeContract({
    buildingId: buildingA.id,
    name: 'Mechanical Piping Package',
    contractType: 'Mechanical',
    authorizedBudget: 2400000,
    authorizedHours: 18000,
    baselineStart: isoDaysAgo(60),
    baselineFinish: isoDaysFromNow(45),
    forecastStart: isoDaysAgo(58),
    forecastFinish: isoDaysFromNow(52),
  });
  const contract2 = makeContract({
    buildingId: buildingA.id,
    name: 'Electrical & Controls',
    contractType: 'Electrical',
    authorizedBudget: 1600000,
    authorizedHours: 11000,
    baselineStart: isoDaysAgo(40),
    baselineFinish: isoDaysFromNow(70),
    forecastStart: isoDaysAgo(40),
    forecastFinish: isoDaysFromNow(75),
  });
  const contract3 = makeContract({
    buildingId: buildingB.id,
    name: 'Central Utility Plant Install',
    contractType: 'Mechanical',
    authorizedBudget: 3100000,
    authorizedHours: 21000,
    baselineStart: isoDaysAgo(90),
    baselineFinish: isoDaysFromNow(20),
    forecastStart: isoDaysAgo(90),
    forecastFinish: isoDaysFromNow(30),
  });
  ds.contracts.push(contract1, contract2, contract3);

  function addActivity(contract, code, name, budget, hours, curveB, curveF, bStartOffset, bFinishOffset, fStartOffset, fFinishOffset, gateSpecs) {
    const act = makeActivity({
      contractId: contract.id,
      code,
      name,
      budget,
      plannedHours: hours,
      baselineStart: isoDaysAgo(bStartOffset),
      baselineFinish: isoDaysFromNow(bFinishOffset),
      forecastStart: isoDaysAgo(fStartOffset),
      forecastFinish: isoDaysFromNow(fFinishOffset),
      baselineCurve: curveB,
      forecastCurve: curveF,
    });
    ds.activities.push(act);
    gateSpecs.forEach((g, idx) => {
      ds.gates.push(
        makeGate({
          activityId: act.id,
          name: g.name,
          weightPct: g.weight,
          completionPct: g.completion,
          statusDate: isoDaysAgo(2),
          notes: g.notes || '',
          updatedBy: admin,
          order: idx,
        })
      );
    });
    return act;
  }

  const act1 = addActivity(
    contract1, 'MP-100', 'Underground Piping Rough-In', 380000, 2600,
    CURVE_TYPES.S_CURVE, CURVE_TYPES.S_CURVE, 55, 5, 53, 3,
    [
      { name: 'Material staged', weight: 15, completion: 100 },
      { name: 'Trenching complete', weight: 20, completion: 100 },
      { name: 'Pipe installed', weight: 40, completion: 70, notes: 'Crew ahead on east wing.' },
      { name: 'Backfill & test', weight: 25, completion: 20 },
    ]
  );

  const act2 = addActivity(
    contract1, 'MP-200', 'Overhead Process Piping', 620000, 4100,
    CURVE_TYPES.FRONT_LOADED, CURVE_TYPES.S_CURVE, 30, 30, 28, 35,
    [
      { name: 'Spool fabrication', weight: 30, completion: 100 },
      { name: 'Hangers & supports', weight: 20, completion: 60 },
      { name: 'Pipe hang & weld', weight: 35, completion: 25 },
      { name: 'Hydro test', weight: 15, completion: 0 },
    ]
  );

  const act3 = addActivity(
    contract2, 'EC-100', 'Conduit & Cable Tray Install', 410000, 2900,
    CURVE_TYPES.LINEAR, CURVE_TYPES.LINEAR, 35, 55, 35, 60,
    [
      { name: 'Layout & supports', weight: 25, completion: 100 },
      { name: 'Conduit install', weight: 45, completion: 55 },
      { name: 'Cable pull', weight: 30, completion: 10 },
    ]
  );

  const act4 = addActivity(
    contract3, 'CUP-050', 'Chiller Skid Set & Piping', 850000, 5600,
    CURVE_TYPES.BACK_LOADED, CURVE_TYPES.BACK_LOADED, 80, 10, 80, 18,
    [
      { name: 'Foundation ready', weight: 10, completion: 100 },
      { name: 'Skid set', weight: 20, completion: 100 },
      { name: 'Piping tie-in', weight: 45, completion: 45 },
      { name: 'Commissioning support', weight: 25, completion: 5 },
    ]
  );

  const period = getOrCreateOpenPeriod(ds.periods, ds.settings.reportingPeriod, ds.settings.statusDate);
  [act1, act2, act3, act4].forEach((act, i) => {
    for (let w = 0; w < 3; w++) {
      ds.actualHours.push(
        makeActualHourRecord({
          activityId: act.id,
          date: isoDaysAgo(w * 7 + 2),
          hours: 60 + i * 20 + w * 5,
          notes: 'Weekly crew hours',
          enteredBy: admin,
          periodId: w === 0 ? period.id : null,
        })
      );
    }
  });

  return ds;
}
