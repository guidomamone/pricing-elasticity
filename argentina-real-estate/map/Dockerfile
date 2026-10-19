FROM nginx:1.27-alpine

COPY site/ /usr/share/nginx/html/

# Barrio polygons from the GCBA open data portal. Optional: if the download fails
# the map falls back to circles, so a portal outage never breaks the build.
ARG BARRIOS_GEOJSON_URL=https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson
RUN wget -q -T 30 -O /usr/share/nginx/html/data/barrios.geojson "$BARRIOS_GEOJSON_URL" \
    && grep -q '"FeatureCollection"' /usr/share/nginx/html/data/barrios.geojson \
    || (echo "barrios.geojson not available, using circles" && rm -f /usr/share/nginx/html/data/barrios.geojson)

EXPOSE 80
HEALTHCHECK CMD wget -q -O /dev/null http://localhost/ || exit 1
