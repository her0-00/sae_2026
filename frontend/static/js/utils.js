/**
 * Utilitaires partagés entre toutes les pages.
 */

export function formatEuro(n) {
  if (n == null) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

export function formatNombre(n) {
  if (n == null) return "—";
  return new Intl.NumberFormat("fr-FR").format(n);
}

export function scoreLabel(score) {
  const map = {
    excellent: "Excellent deal",
    bon:       "Bon prix",
    correct:   "Prix correct",
    cher:      "Cher",
  };
  return map[score] || score;
}

export function scoreIcon(score) {
  return { excellent: "🌟", bon: "✅", correct: "🟡", cher: "🔴" }[score] || "❓";
}

export function dpePillHTML(classe) {
  if (!classe) return "—";
  return `<span class="dpe-pill dpe-${classe}">${classe}</span>`;
}

export function showSpinner(containerId) {
  document.getElementById(containerId).innerHTML =
    `<div class="spinner"></div><p class="loading-text">Chargement…</p>`;
}

export function showError(containerId, msg) {
  document.getElementById(containerId).innerHTML =
    `<div class="alert alert-error">${msg}</div>`;
}

/** Debounce — évite les appels API à chaque frappe */
export function debounce(fn, delay = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

/** Autocomplete commune générique */
export async function setupCommuneAutocomplete(inputId, hiddenId, onSelect) {
  const { searchCommunes } = await import("./api.js");
  const input  = document.getElementById(inputId);
  const hidden = document.getElementById(hiddenId);
  let listEl   = null;

  const search = debounce(async (q) => {
    if (q.length < 2) { closeList(); return; }
    try {
      const results = await searchCommunes(q);
      renderList(results);
    } catch (e) { closeList(); }
  }, 250);

  input.addEventListener("input", () => search(input.value));
  document.addEventListener("click", (e) => { if (e.target !== input) closeList(); });

  function renderList(items) {
    closeList();
    if (!items.length) return;
    listEl = document.createElement("ul");
    listEl.className = "autocomplete-list";
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `${item.nom_commune} (${item.commune_code})`;
      li.addEventListener("click", () => {
        input.value  = item.nom_commune;
        hidden.value = item.commune_code;
        closeList();
        if (onSelect) onSelect(item);
      });
      listEl.appendChild(li);
    });
    input.parentElement.style.position = "relative";
    input.parentElement.appendChild(listEl);
  }

  function closeList() {
    if (listEl) { listEl.remove(); listEl = null; }
  }
}
