# Mapa CABA: comprar vs. alquilar

Mapa por barrio que compara el costo mensual de ser dueño de un depto contra lo que cuesta alquilar el mismo depto. Sitio estático (Leaflet + nginx), sin backend ni API keys.

## El modelo

Para cada barrio, con un depto de referencia de `m2` metros:

- **Precio** = USD/m² × m².
- **Alquiler** = precio × rentabilidad bruta / 12. Zonaprop publica la rentabilidad bruta por barrio, así que el alquiler sale de ahí y no depende del tipo de cambio.
- **Costo de ser dueño**, dos modos:
  - *Flujo de caja* (default): cuota completa de la hipoteca UVA + ABL, seguro y mantenimiento. Es tu ejemplo de Miami: "alquilo a 3.000, comprando pagaría 4.200".
  - *Costo económico*: interés (sin amortización, que es ahorro) + costo de oportunidad del anticipo y los gastos de compra + ABL y mantenimiento − apreciación esperada.
- **Ratio** = costo dueño / alquiler. Menor a 1: comprar cuesta menos que alquilar, el barrio está barato respecto de sus alquileres.

Las expensas quedan afuera de los dos lados porque en Argentina las ordinarias las paga el inquilino.

Supuestos por default (editables en el panel): 50 m², 75% financiado, 6,7% TNA UVA (Banco Nación, octubre 2026), 20 años, 0,8% anual de ABL + seguro + mantenimiento, 7% de gastos de compra, 4% de costo de oportunidad.

Ojo: la tasa UVA es real (ajusta por inflación en pesos), no en dólares. El modelo la trata como una tasa en USD, lo que vale mientras el tipo de cambio real se mantenga estable.

## Capas

- Dueño / alquiler (ratio)
- Rentabilidad bruta
- USD/m²
- Años de alquiler para pagar el depto (price-to-rent)

Los barrios con borde punteado tienen al menos un dato estimado. El check "Solo barrios verificados" los oculta.

## Datos

`site/data/caba.json`. Cada barrio tiene `usd_m2`, `gross_yield` y la fuente de cada uno. Para actualizar: abrir el [Zonaprop Index](https://www.zonaprop.com.ar/blog/) del mes y copiar precio y rentabilidad por barrio. Los datos marcados `estimado` se imputaron con una curva rentabilidad-vs-precio ajustada sobre los barrios verificados, así que su ratio no aporta información propia hasta que se reemplacen.

Polígonos: el build de Docker intenta bajar `barrios.geojson` del portal de datos abiertos del GCBA. Si falla, el mapa dibuja círculos. Para fijarlo, poné el archivo en `site/data/barrios.geojson` (propiedad `BARRIO` o `nombre`) y commitealo.

## Propiedades (planilla "Oportunidades Zona Norte")

La pestaña **Planilla** muestra la hoja Oportunidades (100 propiedades curadas) y Todos los avisos (~3.000). Las oportunidades también se marcan en el mapa, coloreadas por cuánto está su USD/m² debajo de la referencia de su barrio y tipo.

Para actualizar cuando cambie la planilla: descargarla como .xlsx y correr

    python3 scripts/import_sheet.py ~/Downloads/Oportunidades_Zona_Norte.xlsx

Eso regenera `site/data/oportunidades.json` y `site/data/avisos.json` (requiere `pip install openpyxl`). Commitear y pushear.

Ubicación: el import pone cada propiedad en el centro de su barrio (borde punteado en el mapa). En el build de Netlify, `scripts/geocode.mjs` busca cada dirección en la API Georef del gobierno y la mueve a su lugar real si el resultado cae a menos de 3 km del barrio. Si Georef no responde, quedan las posiciones aproximadas y el deploy sigue.

## Correr local

    cd argentina-real-estate/map/site && python3 -m http.server 8000
    # abrir http://localhost:8000

Tests del modelo: `cd argentina-real-estate/map && npm test`

## Deploy en Netlify (recomendado)

Proyecto: `caba-comprar-vs-alquilar` (https://caba-comprar-vs-alquilar.netlify.app).

1. En Netlify: **Project configuration → Build & deploy → Link repository → GitHub** y elegir `guidomamone/pricing-elasticity`.
2. **Branch to deploy:** `main` (o la branch donde esté esto).
3. **Base directory:** `argentina-real-estate/map`. El comando de build y la carpeta a publicar salen de `netlify.toml`.
4. Deploy. Cada push a esa branch redeploya solo, y el build baja los polígonos de barrios del GCBA.

## Deploy en Coolify (alternativa con servidor propio)

Coolify es open source y gratis, pero se instala en un servidor propio. Necesitás una VPS (Oracle Cloud tiene una VM gratis, Hetzner o DigitalOcean cobran unos pocos dólares por mes). La alternativa es Coolify Cloud, que es pago.

1. En la VPS: `curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash`, después abrir `http://<ip>:8000` y crear el usuario admin.
2. **+ New → Resource**. Si el repo es privado, conectá GitHub con la GitHub App de Coolify. Si es público, usá *Public Repository*.
3. Repo `guidomamone/pricing-elasticity`, branch donde esté mergeado esto.
4. **Build Pack: Dockerfile**, **Base Directory: `/argentina-real-estate/map`**, **Ports Exposes: `80`**.
5. Asignar dominio (o usar el sslip.io que genera Coolify) y **Deploy**. Con auto-deploy activado, cada push a esa branch redeploya.
