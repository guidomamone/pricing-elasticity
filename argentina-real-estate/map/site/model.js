// Own vs rent model. All amounts in USD per month unless noted.

export const DEFAULTS = {
  m2: 50,              // reference unit size
  ltv: 0.75,           // share of price financed
  rate: 0.067,         // mortgage TNA (UVA, real rate)
  years: 20,
  closing: 0.07,       // escritura + escribano + comision comprador, % of price
  oppRate: 0.04,       // what the cash (down payment + closing) earns elsewhere, annual
  carry: 0.008,        // ABL + seguro + mantenimiento, % of price per year
  appreciation: 0,     // expected annual price change, only used in "economic" mode
  mode: "cash",        // "cash" = cuota completa + gastos; "economic" = interes + costo de oportunidad - apreciacion
};

export function mortgagePayment(principal, annualRate, years) {
  const n = years * 12;
  const r = annualRate / 12;
  if (principal <= 0) return 0;
  if (r === 0) return principal / n;
  return (principal * r) / (1 - Math.pow(1 + r, -n));
}

export function ownVsRent(barrio, p = DEFAULTS) {
  const price = barrio.usd_m2 * p.m2;
  const rent = (price * barrio.gross_yield) / 100 / 12;
  const loan = price * p.ltv;
  const cash = price * (1 - p.ltv) + price * p.closing;
  const carry = (price * p.carry) / 12;

  let own;
  if (p.mode === "economic") {
    own = (loan * p.rate) / 12 + (cash * p.oppRate) / 12 + carry - (price * p.appreciation) / 12;
  } else {
    own = mortgagePayment(loan, p.rate, p.years) + carry;
  }

  return {
    price,
    rent,
    own,
    ratio: own / rent,
    priceToRentYears: price / (rent * 12),
    cashNeeded: cash,
  };
}

// Buckets for the main layer. Ratio < 1 means owning costs less than renting the same unit.
export const RATIO_BUCKETS = [
  { max: 1.0, color: "#1a9850", label: "< 1.0  comprar cuesta menos que alquilar" },
  { max: 1.3, color: "#91cf60", label: "1.0 – 1.3" },
  { max: 1.7, color: "#fee08b", label: "1.3 – 1.7" },
  { max: 2.2, color: "#fc8d59", label: "1.7 – 2.2" },
  { max: Infinity, color: "#d73027", label: "> 2.2  muy caro vs. alquiler" },
];

export function ratioColor(ratio) {
  return RATIO_BUCKETS.find((b) => ratio < b.max).color;
}
