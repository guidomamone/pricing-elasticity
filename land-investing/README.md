# land-investing

Brainstorm + MVP for a Florida land hold-and-sell model. Start with `BRAINSTORM.md`, `ARCHITECTURE.md`, `MVP.md`.

## Run the MVP map (population layer)
```
cd land-investing
pip install -r requirements.txt
python scripts/build_population.py        # writes map/data/population.geojson
python -m http.server -d map 8000         # open http://localhost:8000
```
Needs internet access to www2.census.gov, unpkg.com, tiles.openfreemap.org.
