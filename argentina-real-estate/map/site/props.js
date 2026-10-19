// Properties from the "Oportunidades Zona Norte" sheet, drawn as markers.

export const DISCOUNT_BUCKETS = [
  { min: 0.5, color: "#1a9850", label: "> 50% bajo referencia" },
  { min: 0.45, color: "#91cf60", label: "45 – 50%" },
  { min: 0.4, color: "#fee08b", label: "40 – 45%" },
  { min: -Infinity, color: "#fc8d59", label: "< 40%" },
];

export const discountColor = (d) => DISCOUNT_BUCKETS.find((b) => (d ?? -1) >= b.min).color;

const usd = (v) => (v == null ? "–" : "US$ " + Math.round(v).toLocaleString("es-AR"));
const pct = (v) => (v == null ? "–" : Math.round(v * 100) + "%");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function propPopup(p) {
  const row = (k, v) => (v == null || v === "" ? "" : `<dt>${k}</dt><dd>${v}</dd>`);
  return `<div class="pop">
    <h3>${esc(p.direccion || p.titulo || "Sin dirección")}</h3>
    <div>${esc(p.tipo)} en ${esc(p.barrio)}${p.estado ? ` · ${esc(p.estado)}` : ""}</div>
    <div class="big">${usd(p.precio)}</div>
    <dl>
      ${row("m² cubiertos", p.m2_cub)}
      ${row("m² totales", p.m2_tot)}
      ${row("Ambientes", p.amb)}
      ${row("USD/m² cub.", usd(p.usd_m2))}
      ${row("Referencia USD/m²", usd(p.ref_usd_m2))}
      ${row("Bajo referencia", pct(p.bajo_ref))}
      ${row("Con obra vs. ref.", pct(p.obra_vs_ref))}
    </dl>
    ${p.titulo ? `<div class="notes"><b>${esc(p.titulo)}</b></div>` : ""}
    ${p.valor_arq ? `<div class="notes">Valor arquitectónico: ${esc(p.valor_arq)}</div>` : ""}
    ${p.riesgos ? `<div class="notes">Riesgos: ${esc(p.riesgos)}</div>` : ""}
    ${p.alerta ? `<div class="notes" style="color:#b7791f">Alerta: ${esc(p.alerta)}</div>` : ""}
    ${p.verificacion ? `<div class="notes">${esc(p.verificacion)}</div>` : ""}
    <div class="src">${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">Ver aviso en ${esc(p.portal || "portal")}</a>` : ""}
      ${p.approx ? " · Ubicación aproximada (centro del barrio)" : ""}</div>
  </div>`;
}

export function propMarker(p) {
  const size = 14;
  const icon = L.divIcon({
    className: "",
    html: `<div class="prop-marker${p.approx ? " approx" : ""}" style="width:${size}px;height:${size}px;background:${discountColor(p.bajo_ref)}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
  return L.marker([p.lat, p.lon], { icon, title: p.direccion || p.titulo || "" }).bindPopup(propPopup(p), { maxWidth: 320 });
}
