# Argentina real estate

Mapa de fuentes de datos para analizar inversiones inmobiliarias en Argentina (foco CABA y AMBA).

## La diferencia con USA

En USA hay MLS, registros públicos de ventas con precio de cierre y APIs como RentCast o ATTOM. En Argentina no existe nada de eso:

- No hay MLS. Cada inmobiliaria publica en portales y los precios son **de publicación (asking)**, no de cierre. El descuento de negociación suele ser relevante y no se publica de forma sistemática.
- Los precios de venta se cotizan en **USD**, los alquileres casi siempre en **ARS**. Cualquier cálculo de rentabilidad depende del tipo de cambio que uses (oficial, MEP, CCL).
- Los portales (Zonaprop, Argenprop, Mercado Libre) no tienen API pública de búsqueda. Scrapear va contra sus términos de uso.
- Los registros de la propiedad (RPI) no son consultables masivamente ni gratis.

Conclusión: se trabaja combinando índices agregados (gratis, mensuales) con relevamiento propio de avisos para una zona específica.

## Fuentes

### Precios de venta y alquiler (avisos)

| Fuente | Qué da | Acceso |
|---|---|---|
| [Zonaprop Index](https://www.zonaprop.com.ar/blog/) | USD/m² por barrio, alquiler medio, rentabilidad bruta, años de recupero. CABA, GBA y otras ciudades | PDF mensual gratis. Hay que parsear el PDF |
| Argenprop / Mercado Libre Inmuebles | Avisos individuales | Sin API pública de búsqueda. La API de Mercado Libre requiere token OAuth y está orientada a publicar, no a buscar |
| Reporte Inmobiliario | Precios, valores de cierre estimados, costos | Pago |
| Properati Data | Dataset histórico de avisos (CSV / BigQuery) | Gratis pero desactualizado, útil para históricos |

### Transacciones reales (escrituras)

| Fuente | Qué da | Acceso |
|---|---|---|
| [Colegio de Escribanos CABA](https://www.colegio-escribanos.org.ar/) | Cantidad y monto de escrituras de compraventa e hipotecas, mensual | Informe web mensual, gratis. Es el mejor proxy de volumen real |
| Colegio de Escribanos Provincia de Buenos Aires | Lo mismo para PBA, por partido | Informe mensual |
| Dirección de Estadística y Censos CABA | Precios de oferta por barrio, series históricas | Datos abiertos CABA |

### Macro y ajustes (sí tienen API)

| Fuente | Qué da |
|---|---|
| [API de Series de Tiempo](https://apis.datos.gob.ar/series/api/) (datos.gob.ar) | UVA, CER, ICC (costo de construcción INDEC), IPC, tipo de cambio. JSON/CSV, sin key |
| [API del BCRA](https://www.bcra.gob.ar/BCRAyVos/catalogo-de-APIs-banco-central.asp) | Variables monetarias, tipo de cambio oficial, UVA, ICL, préstamos hipotecarios |
| dolarapi.com / bluelytics | Dólar MEP, CCL, blue (no oficiales, gratis) |
| [Buenos Aires Data](https://data.buenosaires.gob.ar/) | Datasets CKAN de la Ciudad: parcelas, código urbanístico, barrios |
| USIG / Ciudad 3D (CABA) | Geocodificación, datos de parcela, capacidad constructiva |

## Plan propuesto para esta sección

1. **Ingesta del Zonaprop Index**: bajar los PDFs mensuales, extraer USD/m² y alquiler por barrio a un CSV histórico.
2. **Escrituras**: serie mensual de compraventas e hipotecas del Colegio de Escribanos (volumen real vs. precio de aviso).
3. **Macro**: UVA, ICC y dólar MEP desde la API de Series de Tiempo y el BCRA, para pasar alquileres a USD y medir costo de reposición.
4. **Rentabilidad por barrio**: yield bruto = alquiler anual en USD / precio de venta, con sensibilidad al tipo de cambio y a un descuento de negociación supuesto.
5. **Alertas** (como `miami-rental-alerts`): solo si se encuentra una fuente de avisos con acceso permitido. Hoy no la hay gratis.

Nota de contexto: desde el DNU 70/2023 la ley de alquileres quedó derogada, así que los contratos nuevos pactan libremente plazo, moneda y ajuste. El ICL sigue publicándose para contratos viejos.
