// Build step: refine oportunidades.json coordinates with the national Georef API.
// Never fails the build: properties it can't place keep their approximate barrio position.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const GEOREF = "https://apis.datos.gob.ar/georef/api/direcciones";
const MAX_DISTANCE_KM = 3; // a hit farther than this from the barrio centroid is treated as wrong

const GBA_DEPARTAMENTO = {
  "vicente lopez": "Vicente López", florida: "Vicente López", olivos: "Vicente López", "la lucila": "Vicente López",
  martinez: "San Isidro", acassuso: "San Isidro", "san isidro": "San Isidro", beccar: "San Isidro",
};

const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export function cleanAddress(dir) {
  return (dir || "").replace(/\s+(piso|pb|p\.b\.|depto|dto|uf|unidad|lote)\b.*$/i, "").trim();
}

export function buildQuery(item) {
  const q = { direccion: cleanAddress(item.direccion), max: 1 };
  if (item.zona && norm(item.zona).startsWith("caba")) {
    q.provincia = "02";
  } else {
    q.provincia = "06";
    const dep = GBA_DEPARTAMENTO[norm(item.barrio)];
    if (dep) q.departamento = dep;
  }
  return q;
}

export function distanceKm(a, b) {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

// Mutates items in place; returns how many were placed precisely.
export function applyResults(items, resultados) {
  let placed = 0;
  items.forEach((item, i) => {
    const hit = resultados[i]?.direcciones?.[0]?.ubicacion;
    if (!hit || hit.lat == null || hit.lon == null) return;
    if (distanceKm(item, hit) > MAX_DISTANCE_KM) return;
    item.lat = hit.lat;
    item.lon = hit.lon;
    item.approx = false;
    placed++;
  });
  return placed;
}

async function main(path) {
  const data = JSON.parse(readFileSync(path, "utf8"));
  try {
    const withAddress = data.items.filter((i) => cleanAddress(i.direccion));
    const res = await fetch(GEOREF, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direcciones: withAddress.map(buildQuery) }),
      signal: AbortSignal.timeout(60_000),
    });
    if (!res.ok) throw new Error(`Georef HTTP ${res.status}`);
    const { resultados } = await res.json();
    const placed = applyResults(withAddress, resultados || []);
    data.geocoded = new Date().toISOString();
    writeFileSync(path, JSON.stringify(data));
    console.log(`geocode: ${placed}/${data.items.length} propiedades ubicadas por dirección`);
  } catch (err) {
    console.log(`geocode: sin geocodificar (${err.message}); se usan posiciones aproximadas por barrio`);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main(process.argv[2] || new URL("../site/data/oportunidades.json", import.meta.url));
}
