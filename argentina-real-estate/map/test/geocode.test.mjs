import { test } from "node:test";
import assert from "node:assert/strict";
import { cleanAddress, buildQuery, applyResults } from "../scripts/geocode.mjs";

test("cleanAddress drops floor and unit suffixes", () => {
  assert.equal(cleanAddress("Cullen 5200 Piso 1"), "Cullen 5200");
  assert.equal(cleanAddress("Av. Cabildo 1100 PB"), "Av. Cabildo 1100");
  assert.equal(cleanAddress("Av. Libertador 1100 piso 1"), "Av. Libertador 1100");
  assert.equal(cleanAddress("Melián 4300"), "Melián 4300");
});

test("buildQuery picks provincia and GBA departamento", () => {
  assert.deepEqual(buildQuery({ zona: "CABA norte", barrio: "Saavedra", direccion: "Melián 4300" }),
    { direccion: "Melián 4300", max: 1, provincia: "02" });
  assert.deepEqual(buildQuery({ zona: "GBA norte", barrio: "Béccar", direccion: "Julián Navarro 35" }),
    { direccion: "Julián Navarro 35", max: 1, provincia: "06", departamento: "San Isidro" });
});

test("applyResults keeps nearby hits and rejects far or missing ones", () => {
  const items = [
    { lat: -34.55, lon: -58.48, approx: true },
    { lat: -34.55, lon: -58.48, approx: true },
    { lat: -34.55, lon: -58.48, approx: true },
  ];
  const placed = applyResults(items, [
    { direcciones: [{ ubicacion: { lat: -34.556, lon: -58.485 } }] },
    { direcciones: [{ ubicacion: { lat: -34.90, lon: -58.48 } }] }, // ~39 km away
    { direcciones: [] },
  ]);
  assert.equal(placed, 1);
  assert.equal(items[0].approx, false);
  assert.equal(items[0].lat, -34.556);
  assert.equal(items[1].approx, true);
  assert.equal(items[2].approx, true);
});
