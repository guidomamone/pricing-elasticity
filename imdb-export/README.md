# imdb-export

Scripts para exportar tus calificaciones de IMDb cuando el export oficial da timeout, y a partir de ellas recomendar películas por director, con disponibilidad en streaming.

Todo corre en tu máquina con Python 3.9 o superior. Los datos personales, la sesión de IMDb y la clave de TMDB no se guardan en el repo (ver `.gitignore`).

## Archivos

| Script | Para qué sirve |
|---|---|
| `scrape.py` | Abre Chromium con Playwright, recorre tu lista de calificaciones página por página y guarda `ratings_raw.csv`. IMDb corta cada lista en 40 páginas de 250, así que con más de 10.000 calificaciones hay que correrlo varias veces con filtros (por tipo de título) y renombrar cada salida a `ratings_partN.csv`. |
| `merge.py` | Une todos los `ratings_part*.csv`, quita duplicados y escribe `ratings_final.csv`. |
| `directors.py` | Cruza tus calificaciones con los datasets públicos de IMDb. Genera las listas de directores y los candidatos de animación. |
| `enrich.py` | Consulta TMDB: idioma original (para filtrar cine indio y separar anime) y plataformas de streaming. Escribe los `final_*.csv`. |
| `view.py` | Muestra las 5 listas, 20 por página (`python3 view.py 2` para la siguiente). |

## Requisitos

```
python3 -m pip install playwright
python3 -m playwright install chromium
```

Datasets de IMDb (gratis para uso personal), en una carpeta `imdb_data/`:

```
mkdir -p imdb_data && cd imdb_data
for f in title.basics title.ratings title.crew title.akas name.basics; do
  curl -O https://datasets.imdbws.com/$f.tsv.gz
done
cd ..
```

Clave de TMDB (gratis, themoviedb.org, Settings, API). Se guarda solo en la sesión de la terminal, sin escribirla en ningún archivo:

```
read -s "TMDB_KEY?Pega tu clave de TMDB y apreta Enter: "
export TMDB_KEY
```

## Uso

1. `python3 scrape.py` (una vez por cada tramo de la lista), renombrar cada `ratings_raw.csv` a `ratings_partN.csv`.
2. `python3 merge.py`
3. `python3 directors.py` (6 a 10 minutos, por `title.akas`)
4. `python3 enrich.py` (segundos si ya hay caché en `tmdb_cache.json`)
5. `python3 view.py`

## Listas

1. Directores de los que calificaste 2 o más películas, con sus películas pendientes.
2. Directores de los que calificaste 1 película (con 8 o más), para seguir explorando.
3. Directores nuevos que podrían gustarte.
4. Películas de animación que no son anime.
5. Películas de anime (animación con idioma original japonés).

## Ajustes

Están como constantes al principio de cada script.

- `directors.py`: `MIN_VOTES`, `MIN_RATING`, `LIKE_THRESHOLD`, `EXPLORE_MIN_RATING`, `GENRE_FIT_WEIGHT`, `EXCLUDE_LANGS`, `EXCLUDE_NAMES`.
- `enrich.py`: `SHOW_COUNTRIES`, `SERVICES` (tus plataformas), `DISABLED_SERVICES`, `MIN_RUNTIME`, `STREAM_KEYS`.

Si cambiás `EXCLUDE_LANGS` en uno, ponelo igual en el otro.

### Excepción temporal por servicio o país

Sin tocar la configuración de siempre, `enrich.py` y `view.py` aceptan variables de entorno. Los resultados van a archivos con prefijo, así que los `final_*.csv` normales no se pisan:

```
ENRICH_ONLY=Netflix ENRICH_PREFIX=netflix_ python3 enrich.py
VIEW_PREFIX=netflix_ python3 view.py
```

- `ENRICH_ONLY`: un solo servicio (Paramount+, Peacock, Netflix, Disney+, Hulu, Prime Video, Apple TV, HBO Max, Crunchyroll o Tubi).
- `ENRICH_COUNTRIES`: `AR`, `US` o `AR,US` (por defecto, lo que diga `SHOW_COUNTRIES`).
- `ENRICH_PREFIX` y `VIEW_PREFIX`: prefijo de los archivos de salida.

## Notas

- El filtro de cine indio usa el idioma original que informa TMDB. `directors.py` hace una primera pasada aproximada con `title.akas` para no consultar de más.
- Solo se consideran películas (`movie` y `tvMovie`). Las que viste pero nunca calificaste pueden aparecer como pendientes.
- Datos de streaming: JustWatch, a través de TMDB.
