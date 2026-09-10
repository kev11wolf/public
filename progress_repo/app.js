// app.js — Bootstraps the Contract Progress Tracker application.
import { initDataset } from './src/store.js';
import { createApp } from './src/ui.js';

async function main() {
  const root = document.getElementById('app-root');
  const dataset = await initDataset();
  window.__cpt = createApp(root, dataset);
}

document.addEventListener('DOMContentLoaded', main);
