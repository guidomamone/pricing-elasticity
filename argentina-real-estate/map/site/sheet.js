// Spreadsheet view of the sheet data: search, filters, sortable columns.

const usd = (v) => (v == null || v === "" ? "" : Math.round(v).toLocaleString("es-AR"));
const pct = (v) => (v == null || v === "" ? "" : Math.round(v * 100) + "%");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const COLUMNS = {
  oportunidades: [
    { key: "id", label: "#" },
    { key: "barrio", label: "Barrio", cls: "l" },
    { key: "tipo", label: "Tipo", cls: "l" },
    { key: "direccion", label: "Dirección", cls: "l", map: true },
    { key: "precio", label: "Precio USD", fmt: usd },
    { key: "m2_cub", label: "m² cub." },
    { key: "m2_tot", label: "m² tot." },
    { key: "amb", label: "Amb." },
    { key: "estado", label: "Estado", cls: "l" },
    { key: "usd_m2", label: "USD/m²", fmt: usd },
    { key: "ref_usd_m2", label: "Ref. USD/m²", fmt: usd },
    { key: "bajo_ref", label: "% bajo ref.", fmt: pct },
    { key: "obra_vs_ref", label: "Con obra vs. ref.", fmt: pct },
    { key: "url", label: "Aviso", link: true },
    { key: "titulo", label: "Título", cls: "wrap" },
    { key: "riesgos", label: "Riesgos", cls: "wrap" },
    { key: "alerta", label: "Alerta de datos", cls: "wrap" },
    { key: "notas", label: "Notas", cls: "wrap" },
    { key: "verificacion", label: "Verificación", cls: "wrap" },
  ],
  avisos: [
    { key: "barrio", label: "Barrio", cls: "l" },
    { key: "tipo", label: "Tipo", cls: "l" },
    { key: "direccion", label: "Dirección", cls: "l" },
    { key: "precio", label: "Precio USD", fmt: usd },
    { key: "m2_cub", label: "m² cub." },
    { key: "m2_tot", label: "m² tot." },
    { key: "amb", label: "Amb." },
    { key: "estado", label: "Estado", cls: "l" },
    { key: "usd_m2", label: "USD/m²", fmt: usd },
    { key: "ref_usd_m2", label: "Ref. USD/m²", fmt: usd },
    { key: "bajo_ref", label: "% bajo ref.", fmt: pct },
    { key: "url", label: "Aviso", link: true },
    { key: "valor_arq", label: "Valor arquitectónico", cls: "wrap" },
    { key: "riesgos", label: "Riesgos", cls: "wrap" },
  ],
};

const MAX_ROWS = 500;

export function initSheet({ oportunidades, loadAvisos, onShowOnMap }) {
  const state = { sheet: "oportunidades", sort: { key: "bajo_ref", asc: false }, rows: { oportunidades: oportunidades.items } };
  const $ = (id) => document.getElementById(id);

  async function rowsFor(sheet) {
    if (!state.rows[sheet]) {
      $("sheetCount").textContent = "Cargando…";
      const d = await loadAvisos();
      state.rows[sheet] = d.rows.map((r) => Object.fromEntries(d.cols.map((c, i) => [c, r[i]])));
    }
    return state.rows[sheet];
  }

  function fillSelect(el, values, allLabel) {
    const current = el.value;
    el.innerHTML = `<option value="">${allLabel}</option>` +
      [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "es")).map((v) => `<option>${esc(v)}</option>`).join("");
    el.value = [...el.options].some((o) => o.value === current) ? current : "";
  }

  async function render() {
    const cols = COLUMNS[state.sheet];
    const all = await rowsFor(state.sheet);
    document.querySelectorAll("#sheetTabs button").forEach((b) => b.classList.toggle("on", b.dataset.sheet === state.sheet));
    fillSelect($("sheetBarrio"), all.map((r) => r.barrio), "Todos los barrios");
    fillSelect($("sheetTipo"), all.map((r) => r.tipo), "Todos los tipos");

    const q = norm($("sheetSearch").value);
    const barrio = $("sheetBarrio").value;
    const tipo = $("sheetTipo").value;
    let rows = all.filter((r) =>
      (!barrio || r.barrio === barrio) &&
      (!tipo || r.tipo === tipo) &&
      (!q || norm(Object.values(r).join(" ")).includes(q)));

    const { key, asc } = state.sort;
    rows = rows.slice().sort((a, b) => {
      const x = a[key], y = b[key];
      if (x == null || x === "") return 1;
      if (y == null || y === "") return -1;
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "es");
      return asc ? c : -c;
    });

    $("sheetCount").textContent = rows.length > MAX_ROWS
      ? `Mostrando ${MAX_ROWS} de ${rows.length}. Filtrá para ver el resto.`
      : `${rows.length} filas`;

    document.querySelector("#sheet thead").innerHTML = "<tr>" + cols.map((c) =>
      `<th data-key="${c.key}" class="${c.cls || ""}${c.key === key ? " sorted" + (asc ? " asc" : "") : ""}">${c.label}</th>`).join("") + "</tr>";
    document.querySelector("#sheet tbody").innerHTML = rows.slice(0, MAX_ROWS).map((r) => "<tr>" + cols.map((c) => {
      const v = r[c.key];
      let html;
      if (c.link) html = v ? `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(r.portal || "Ver")}</a>` : "";
      else if (c.map && r.lat != null) html = `<a href="#mapa" data-show="${r.id}">${esc(v || "(sin dirección)")}</a>`;
      else html = c.fmt ? c.fmt(v) : esc(v);
      return `<td class="${c.cls || ""}">${html}</td>`;
    }).join("") + "</tr>").join("");

    document.querySelectorAll("#sheet th").forEach((th) => {
      th.onclick = () => {
        const k = th.dataset.key;
        state.sort = { key: k, asc: state.sort.key === k ? !state.sort.asc : true };
        render();
      };
    });
    document.querySelectorAll("#sheet a[data-show]").forEach((a) => {
      a.onclick = () => onShowOnMap(Number(a.dataset.show));
    });
  }

  document.querySelectorAll("#sheetTabs button").forEach((b) => {
    b.onclick = () => {
      state.sheet = b.dataset.sheet;
      if (!COLUMNS[state.sheet].some((c) => c.key === state.sort.key)) state.sort = { key: "bajo_ref", asc: false };
      render();
    };
  });
  ["sheetSearch", "sheetBarrio", "sheetTipo"].forEach((id) => ($(id).oninput = render));
  $("sheetMeta").textContent = `Fuente: ${oportunidades.source}, importada ${oportunidades.imported}. ` +
    `"Con obra vs. ref." supone un reciclado de US$ ${oportunidades.costo_reciclado_m2}/m². Precios de publicación.`;
  render();
}
