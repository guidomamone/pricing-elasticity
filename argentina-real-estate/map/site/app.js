import { DEFAULTS, ownVsRent, RATIO_BUCKETS, ratioColor } from "./model.js";

const PARAMS = [
  { key: "m2", label: "Superficie (m²)", step: 5, scale: 1 },
  { key: "ltv", label: "Financiación (% del precio)", step: 5, scale: 100 },
  { key: "rate", label: "Tasa hipotecaria UVA (TNA %)", step: 0.1, scale: 100 },
  { key: "years", label: "Plazo (años)", step: 1, scale: 1 },
  { key: "carry", label: "ABL + seguro + mant. (% anual)", step: 0.1, scale: 100 },
  { key: "closing", label: "Gastos de compra (%)", step: 0.5, scale: 100, modes: ["economic"] },
  { key: "oppRate", label: "Costo de oportunidad (% anual)", step: 0.5, scale: 100, modes: ["economic"] },
  { key: "appreciation", label: "Apreciación esperada (% anual)", step: 0.5, scale: 100, modes: ["economic"] },
];

const MODE_HINT = {
  cash: "Cuota completa de la hipoteca + ABL, seguro y mantenimiento. Es lo que sale de tu bolsillo cada mes. Las expensas se excluyen porque las paga el inquilino también.",
  economic: "Interés (no amortización) + costo de oportunidad del anticipo y los gastos de compra + ABL y mantenimiento − apreciación esperada.",
};

const LAYERS = {
  ratio: {
    label: "Dueño / alquiler",
    value: (r) => r.ratio,
    color: (v) => ratioColor(v),
    format: (v) => v.toFixed(2) + "x",
    legend: () => RATIO_BUCKETS.map((b) => [b.color, b.label]),
  },
  yield: {
    label: "Rentabilidad bruta",
    value: (r, b) => b.gross_yield,
    color: (v) => scale(v, [4, 5, 6, 7, 8], ["#d73027", "#fc8d59", "#fee08b", "#91cf60", "#1a9850"]),
    format: (v) => v.toFixed(1) + "%",
    legend: () => [["#d73027", "< 4%"], ["#fc8d59", "4 – 5%"], ["#fee08b", "5 – 6%"], ["#91cf60", "6 – 7%"], ["#1a9850", "> 7%"]],
  },
  price: {
    label: "USD/m²",
    value: (r, b) => b.usd_m2,
    color: (v) => scale(v, [1500, 2000, 2500, 3000, 4000], ["#f1eef6", "#bdc9e1", "#74a9cf", "#2b8cbe", "#045a8d", "#023858"]),
    format: (v) => "US$ " + fmt(v),
    legend: () => [["#f1eef6", "< 1.500"], ["#bdc9e1", "1.500 – 2.000"], ["#74a9cf", "2.000 – 2.500"], ["#2b8cbe", "2.500 – 3.000"], ["#045a8d", "3.000 – 4.000"], ["#023858", "> 4.000"]],
  },
  ptr: {
    label: "Años de alquiler",
    value: (r) => r.priceToRentYears,
    color: (v) => scale(v, [12, 15, 18, 22, 28], ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027", "#a50026"]),
    format: (v) => v.toFixed(1) + " años",
    legend: () => [["#1a9850", "< 12"], ["#91cf60", "12 – 15"], ["#fee08b", "15 – 18"], ["#fc8d59", "18 – 22"], ["#d73027", "22 – 28"], ["#a50026", "> 28"]],
  },
};

function scale(v, breaks, colors) {
  const i = breaks.findIndex((b) => v < b);
  return colors[i === -1 ? colors.length - 1 : i];
}
const fmt = (v) => Math.round(v).toLocaleString("es-AR");
const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().trim();
const isVerified = (b) => !b.src_price.startsWith("estimado") && !b.src_yield.startsWith("estimado");

const state = { params: { ...DEFAULTS }, layer: "ratio", verifiedOnly: false };
let data, map, polygons = null, shapes = new Map();

async function main() {
  data = await (await fetch("data/caba.json")).json();
  map = L.map("map", { zoomControl: true }).setView(data.center, data.zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  polygons = await loadPolygons();
  buildControls();
  render();
}

// Barrio polygons are optional: the Docker build tries to download them from the GCBA open data portal.
// Without them each barrio is drawn as a circle at its centroid.
async function loadPolygons() {
  try {
    const res = await fetch("data/barrios.geojson");
    if (!res.ok) return null;
    const gj = await res.json();
    const byName = new Map();
    for (const f of gj.features || []) {
      const p = f.properties || {};
      const name = p.BARRIO || p.barrio || p.nombre || p.NOMBRE;
      if (name) byName.set(norm(name), f);
    }
    return byName.size ? byName : null;
  } catch {
    return null;
  }
}

function buildControls() {
  const layers = document.getElementById("layers");
  for (const [key, def] of Object.entries(LAYERS)) {
    const b = document.createElement("button");
    b.textContent = def.label;
    b.dataset.layer = key;
    b.onclick = () => { state.layer = key; render(); };
    layers.append(b);
  }

  document.querySelectorAll("#mode button").forEach((b) => {
    b.onclick = () => { state.params.mode = b.dataset.mode; render(); };
  });

  const params = document.getElementById("params");
  for (const p of PARAMS) {
    const row = document.createElement("div");
    row.className = "param";
    row.dataset.modes = (p.modes || ["cash", "economic"]).join(" ");
    const id = "p-" + p.key;
    row.innerHTML = `<label for="${id}">${p.label}</label><input type="number" id="${id}" step="${p.step}">`;
    const input = row.querySelector("input");
    input.value = +(state.params[p.key] * p.scale).toFixed(2);
    input.oninput = () => {
      const v = parseFloat(input.value);
      if (Number.isFinite(v)) { state.params[p.key] = v / p.scale; render(); }
    };
    params.append(row);
  }

  document.getElementById("verifiedOnly").onchange = (e) => { state.verifiedOnly = e.target.checked; render(); };
  document.getElementById("togglePanel").onclick = () => document.getElementById("panel").classList.toggle("open");
  document.getElementById("meta").textContent =
    `Datos: ${data.updated}. Polígonos: ${polygons ? "barrios GCBA" : "no disponibles, se muestran círculos"}.`;
}

function render() {
  const layer = LAYERS[state.layer];
  document.querySelectorAll("#layers button").forEach((b) => b.classList.toggle("on", b.dataset.layer === state.layer));
  document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === state.params.mode));
  document.querySelectorAll(".param").forEach((r) => (r.style.display = r.dataset.modes.includes(state.params.mode) ? "" : "none"));
  document.getElementById("modeHint").textContent = MODE_HINT[state.params.mode];
  document.getElementById("legend").innerHTML = layer.legend()
    .map(([c, l]) => `<div class="legend-row"><span class="swatch" style="background:${c}"></span>${l}</div>`).join("");

  shapes.forEach((s) => s.remove());
  shapes.clear();

  const rows = [];
  for (const b of data.barrios) {
    if (state.verifiedOnly && !isVerified(b)) continue;
    const r = ownVsRent(b, state.params);
    const v = layer.value(r, b);
    const color = layer.color(v);
    const style = { color: "#333", weight: 1, dashArray: isVerified(b) ? null : "4 3", fillColor: color, fillOpacity: 0.7 };
    const feature = polygons && polygons.get(norm(b.name));
    const shape = feature
      ? L.geoJSON(feature, { style: () => style })
      : L.circleMarker([b.lat, b.lon], { ...style, radius: 16 });
    shape.bindPopup(popup(b, r, layer, v));
    shape.bindTooltip(b.name, { permanent: true, direction: "center", className: "map-label" });
    shape.addTo(map);
    shapes.set(b.name, shape);
    rows.push({ b, r });
  }

  rows.sort((x, y) => x.r.ratio - y.r.ratio);
  document.querySelector("#ranking tbody").innerHTML = rows.map(({ b, r }) => `
    <tr data-name="${b.name}">
      <td>${b.name}${isVerified(b) ? "" : ' <span class="est">*</span>'}</td>
      <td><span class="swatch" style="display:inline-block;vertical-align:-2px;background:${ratioColor(r.ratio)}"></span> ${r.ratio.toFixed(2)}</td>
      <td>${fmt(r.own)}</td>
      <td>${fmt(r.rent)}</td>
    </tr>`).join("");
  document.querySelectorAll("#ranking tbody tr").forEach((tr) => {
    tr.onclick = () => {
      const s = shapes.get(tr.dataset.name);
      map.fitBounds(s.getBounds ? s.getBounds() : L.latLng(s.getLatLng()).toBounds(1500), { maxZoom: 14 });
      s.openPopup();
    };
  });
}

function popup(b, r, layer, v) {
  const ars = (usd) => "$ " + fmt(usd * data.fx_ars_usd);
  const est = (src) => (src.startsWith("estimado") ? ` <span class="est">estimado</span>` : ` (${src})`);
  return `<div class="pop">
    <h3>${b.name}</h3>
    <div class="big">${r.ratio.toFixed(2)}x</div>
    <div>${r.ratio < 1 ? "Ser dueño cuesta menos que alquilar" : `Ser dueño cuesta ${Math.round((r.ratio - 1) * 100)}% más que alquilar`}</div>
    <dl>
      <dt>Precio (${state.params.m2} m²)</dt><dd>US$ ${fmt(r.price)}</dd>
      <dt>Costo dueño / mes</dt><dd>US$ ${fmt(r.own)}</dd>
      <dt>Alquiler / mes</dt><dd>US$ ${fmt(r.rent)}</dd>
      <dt></dt><dd>${ars(r.rent)}</dd>
      <dt>Rentabilidad bruta</dt><dd>${b.gross_yield.toFixed(2)}%</dd>
      <dt>Años de alquiler</dt><dd>${r.priceToRentYears.toFixed(1)}</dd>
      <dt>Efectivo necesario</dt><dd>US$ ${fmt(r.cashNeeded)}</dd>
      ${state.layer === "ratio" ? "" : `<dt>${layer.label}</dt><dd>${layer.format(v)}</dd>`}
    </dl>
    <div class="src">Precio${est(b.src_price)}. Rentabilidad${est(b.src_yield)}.</div>
  </div>`;
}

main();
