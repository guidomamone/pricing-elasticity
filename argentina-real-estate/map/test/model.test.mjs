import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mortgagePayment, ownVsRent, ratioColor, DEFAULTS } from "../site/model.js";

test("mortgage payment matches a known amortization", () => {
  // 100k at 6% over 30 years is 599.55/month
  assert.equal(mortgagePayment(100000, 0.06, 30).toFixed(2), "599.55");
  assert.equal(mortgagePayment(12000, 0, 1), 1000);
});

test("rent is derived from gross yield", () => {
  const r = ownVsRent({ usd_m2: 2400, gross_yield: 6 }, { ...DEFAULTS, m2: 50 });
  assert.equal(r.price, 120000);
  assert.equal(r.rent, 600);
  assert.equal(Math.round(r.priceToRentYears * 100) / 100, 16.67);
});

test("cash mode: full payment plus carry", () => {
  const p = { ...DEFAULTS, m2: 100, ltv: 0.5, rate: 0.06, years: 30, carry: 0.012 };
  const r = ownVsRent({ usd_m2: 2000, gross_yield: 6 }, p);
  assert.equal(r.own.toFixed(2), (599.55 + 200).toFixed(2));
});

test("economic mode subtracts appreciation and adds opportunity cost", () => {
  const p = { ...DEFAULTS, m2: 100, mode: "economic", ltv: 0.5, rate: 0.06, closing: 0, oppRate: 0.04, carry: 0, appreciation: 0.02 };
  const r = ownVsRent({ usd_m2: 1200, gross_yield: 6 }, p);
  // interest 300 + opp cost 200 - appreciation 200
  assert.equal(Math.round(r.own), 300);
});

test("higher yield means a lower ratio, all else equal", () => {
  const a = ownVsRent({ usd_m2: 2000, gross_yield: 4 });
  const b = ownVsRent({ usd_m2: 2000, gross_yield: 8 });
  assert.ok(b.ratio < a.ratio);
  assert.notEqual(ratioColor(a.ratio), ratioColor(b.ratio));
});

test("seed data is complete", () => {
  const data = JSON.parse(readFileSync(new URL("../site/data/caba.json", import.meta.url)));
  assert.ok(data.barrios.length > 0);
  for (const b of data.barrios) {
    for (const k of ["name", "lat", "lon", "usd_m2", "gross_yield", "src_price", "src_yield"]) {
      assert.ok(b[k] !== undefined, `${b.name} missing ${k}`);
    }
  }
});
