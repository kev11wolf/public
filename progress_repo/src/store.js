// store.js — IndexedDB-backed persistence with localStorage fallback,
// and JSON import/export as the authoritative portable backup format.
import { emptyDataset, validateDataset, SCHEMA_VERSION } from './schema.js';

const DB_NAME = 'contract-progress-tracker';
const DB_VERSION = 1;
const STORE_NAME = 'dataset';
const RECORD_KEY = 'main';
const LOCAL_STORAGE_KEY = 'cpt_dataset_v' + SCHEMA_VERSION;

let dbPromise = null;
let indexedDbAvailable = true;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      indexedDbAvailable = false;
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => {
      indexedDbAvailable = false;
      reject(req.error);
    };
  });
  return dbPromise;
}

export async function loadDataset() {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.get(RECORD_KEY);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } catch (e) {
    return loadFromLocalStorage();
  }
}

export async function saveDataset(dataset) {
  try {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(dataset, RECORD_KEY);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (e) {
    saveToLocalStorage(dataset);
  }
}

function loadFromLocalStorage() {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function saveToLocalStorage(dataset) {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(dataset));
  } catch (e) {
    console.error('Unable to persist dataset to localStorage', e);
  }
}

export async function initDataset() {
  const existing = await loadDataset();
  if (existing) return existing;
  const fresh = emptyDataset();
  await saveDataset(fresh);
  return fresh;
}

export function exportDatasetToFile(dataset, filenamePrefix) {
  const filename = (filenamePrefix || 'contract-progress-tracker') + '-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.json';
  const blob = new Blob([JSON.stringify(dataset, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function parseImportedJson(text) {
  let obj;
  try {
    obj = JSON.parse(text);
  } catch (e) {
    return { valid: false, errors: ['File is not valid JSON: ' + e.message] };
  }
  const result = validateDataset(obj);
  return { ...result, dataset: obj };
}

export function isIndexedDbAvailable() {
  return indexedDbAvailable;
}
