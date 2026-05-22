/**
 * Client API — toutes les appels vers le backend Flask.
 * BASE_URL est injecté depuis la page HTML ou détecté automatiquement.
 */
const API_BASE = window.API_BASE || "";

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---- Communes ----
export const searchCommunes = (q) =>
  apiFetch(`/api/communes/search?q=${encodeURIComponent(q)}`);

export const getResumeCommune = (code) =>
  apiFetch(`/api/communes/${code}/resume`);

// ---- Estimateur ----
export const estimer = (body) =>
  apiFetch("/api/estimateur", { method: "POST", body: JSON.stringify(body) });

// ---- Carte ----
export const getPrixM2GeoJSON = (params) =>
  apiFetch("/api/carte/prix-m2?" + new URLSearchParams(params));

export const getTransactionsProches = (params) =>
  apiFetch("/api/carte/transactions?" + new URLSearchParams(params));

// ---- Analyses ----
export const getAnalyseDPE       = (p) => apiFetch("/api/analyses/dpe?"       + new URLSearchParams(p));
export const getAnalyseBruit     = (p) => apiFetch("/api/analyses/bruit?"     + new URLSearchParams(p));
export const getAnalyseTransport = (p) => apiFetch("/api/analyses/transport?" + new URLSearchParams(p));
export const getAnalyseTendances = (p) => apiFetch("/api/analyses/tendances?" + new URLSearchParams(p));

// ---- Opportunités ----
export const getOpportunites = (p) =>
  apiFetch("/api/opportunites?" + new URLSearchParams(p));
