# CYPLAN 101 - Final Project

This project looks at which parts of the Bay Area shoreline are most at risk
of flooding during a King Tide in an El Niño winter. We used NOAA's sea level
rise inundation maps to estimate flooding, then checked how many people
(including more vulnerable populations) and how many miles of road fall
inside the flooded areas. Results are ranked and mapped by SFEI's 30
Operational Landscape Units (OLUs), which split the Bay shoreline into
segments.

## Setup

Due to the `fiona` package that's required for geopandas, the Python version is currently limited to 3.12. If your version is higher, first run
`py install 3.12`.

Then (for Bash),
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If using PowerShell, use `.venv\Scripts\Activate.ps1` instead of `source`:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Data

Raw source data lives in `data/`. Two large files are gitignored (download
them yourself per the project doc, they're too big for the repo):

- `data/Bay_Area_Dasymetric_Population_Estimates.gpkg` (~1GB) -- SFEI
  building-level population estimates
- `data/CA_SFBay_slr_final_dist.gpkg` -- NOAA SLR inundation vectors

### `scripts/`

- `extract_olu.py` -- pulls the OLU polygons out of
  `Adaptation_Atlas_Data_SFEI_v3_2021.mpk` (an Esri Map Package / 7z
  archive, not directly readable by geopandas) and writes clean
  GeoPackages to `data/processed/`. Run this first; it's the join
  skeleton everything else gets cut up by.
- `clip_svi.py` -- filters the statewide `SVI2022_CALIFORNIA_tract.gdb`
  down to the 9 Bay Area counties and writes
  `data/processed/svi_bayarea_tracts.gpkg`.
- `prep_roads.py` -- merges the 9 county TIGER road files into one layer
  and reprojects it, writing `data/processed/roads_bayarea.gpkg`.
- `fetch_tide_levels.py` -- downloads CO-OPS hourly water levels (4
  stations x 4 candidate winters) and the RONI ENSO index, and converts
  every water level to NAVD88 using each station's own official datum
  offset. Writes `data/processed/tide_levels_navd88.csv` and
  `data/raw/RONI.ascii.txt`. **See `docs/datum_handling.md`** for why this
  conversion is station-specific and not a single Bay-wide number.
- `fetch_bay_trail.py` -- downloads the Bay Trail layer from the MTC
  feature service (`where=1=1&outFields=*&f=geojson`), writes the raw
  pull to `data/raw/bay_trail.geojson` and a reprojected version to
  `data/processed/bay_trail.gpkg`. Checks for the segment-4032 duplicate
  the planning doc warns about (none found in the raw pull -- see the
  script's docstring for what that does and doesn't mean).
- `fetch_2026_27_predictions.py` -- downloads CO-OPS high/low tide
  *predictions* (not observations) for Nov 2026-Mar 2027, the same 4
  stations, converted to NAVD88 the same way as `fetch_tide_levels.py`.
  Writes `data/processed/tide_predictions_2026_27_navd88.csv`. This is
  the baseline astronomical tide curve to build the King Tide + El Nino
  scenario on top of -- it does not build that scenario itself.
- `exposure_by_olu.py` -- **step 6, exposure analysis.** Overlays the NOAA
  inundation layer (default 2.5 ft, per `docs/scenario_water_level.md`;
  `--scenario-ft` picks another) on population, roads and the Bay Trail,
  and totals everything by OLU into one table:
  `outputs/exposure_by_olu_<scenario>.csv` (+ a `.gpkg` with the OLU
  polygons for mapping). Metrics: acres flooded, people and vulnerable
  people (SVI >= 0.75) exposed, road miles (all + primary/secondary). Population is
  area-weighted (spread evenly over each block group's area -- the
  midterm method; step 11 swaps in SFEI dasymetric). **Needs two files
  not in the repo yet:** `data/CA_SFBay_slr_final_dist.gpkg` (NOAA) and
  `data/processed/block_groups_bayarea.gpkg` (block-group polygons with
  a 12-digit `GEOID` and a `pop` column). Without the block-group file it
  falls back to SVI tracts and labels that in the `pop_unit` column.

Run from the repo root with the venv active:

```bash
python data_processing.py
python scripts/prep_block_groups.py
python scripts/fetch_tide_levels.py
python scripts/fetch_2026_27_predictions.py
python scripts/calc_scenario_water_level.py
python scripts/exposure_by_olu.py
python scripts/make_exposure_map.py
python scripts/visualize_historical_analysis.py
```

### `data/processed/`

- **`olu_primary.gpkg`** -- 30 rows, one polygon per OLU (shoreline + the
  land behind it). **Use this as the join skeleton** for ranking: intersect
  flood polygons / SVI tracts / roads against this to get
  per-OLU totals (acres flooded, people exposed, road/trail miles flooded).
- `olu_all_components.gpkg` -- all 89 rows: each OLU's `Primary`,
  `Submerged`, and `Contributing watershed` polygons, kept for reference
  in case the watershed or submerged extents are needed.
- **`svi_bayarea_tracts.gpkg`** -- 1,765 CDC SVI tracts across the 9 Bay
  Area counties. Key columns: `E_TOTPOP` (population), `RPL_THEMES`
  (overall vulnerability percentile, 0-1; the doc suggests >= 0.75 as the
  "high vulnerability" cutoff), `RPL_THEME1`-`RPL_THEME4` (sub-themes).
- `roads_bayarea.gpkg` -- 151,426 road segments across the 9 counties
  (41,475 mi total), merged + reprojected.
- `tide_levels_navd88.csv` -- hourly tide gauge water levels for 4
  stations x 4 candidate winters, converted to NAVD88. See
  `docs/datum_handling.md`.
- `bay_trail.gpkg` -- 683 Bay Trail segments (560.5 mi total), reprojected.
- `tide_predictions_2026_27_navd88.csv` -- 2,332 predicted high/low tides
  (4 stations x Nov 2026-Mar 2027), converted to NAVD88. Highest predicted
  peaks cluster around late Dec 2026 / late Jan 2027, consistent with
  typical King Tide timing.

All processed layers (vector and tabular) are standardized to
**EPSG:26910** (UTM Zone 10N, meters) horizontally and **NAVD88**
vertically (water levels only -- the other layers have no elevation
component). The raw SVI and TIGER roads files are EPSG:4269; the raw tide
levels are in MHHW, a station-local tidal datum, not an elevation.

**Note:** SVI is 2018-2022 ACS, while the SFEI dasymetric population dataset is 2017-2021 ACS.

### `docs/`

- `datum_handling.md` -- explains why the tide gauge data (MHHW,
  station-local) and the NOAA SLR inundation data (NAVD88, Bay-wide) had
  to be reconciled, the station-specific offsets used, and known gaps in
  the tide gauge data uncovered while pulling it. Written in response to
  Mei's MTC feedback on vertical datum handling.
- `scenario_water_level.md` -- the highest predicted King Tide this
  winter (2026-27) + the 1 ft El Niño bump, expressed as height above
  MHHW, and which NOAA SLR raster scenario that picks (**2.5 ft**).
  Computed by `scripts/calc_scenario_water_level.py`.

### Figures (`outputs/`)

- `exposure_map_2_5ft.png`: Map of how many people would be exposed in
  each OLU at 2.5 ft above MHHW, next to a bar chart of the 12 OLUs with
  the most people exposed. Dark red marks people living in
  high-vulnerability tracts (SVI 0.75 or higher). Suisun and Carquinez are
  hatched because NOAA's SF Bay file doesn't cover them. Across the Bay,
  about 78,000 people are exposed, around 11,000 of them in
  high-vulnerability tracts. San Rafael has the most people exposed
  (about 13,000), and about half of them are in high-vulnerability tracts.

- `historical_analysis/el_nino_historical_visualizations.png`: Four
  panels on the El Niño side of the project. Top left compares water
  levels in three past El Niño winters to nearby normal winters. Only
  1982-83 went past our +1 ft assumption, and 2015-16 barely moved.
  Top right plots El Niño strength (RONI) against the high-water bump.
  With only three winters, this just describes those events and can't
  be used to predict anything. Bottom left shows predicted tide peaks
  for this winter, which are highest in December and January. Bottom
  right ranks the OLUs by people exposed.

### Work In Progress (not built yet)

Block-group polygons + ACS population (input for `exposure_by_olu.py`),
NOAA SLR inundation vectors (gitignored, download locally -- now that
`docs/scenario_water_level.md` says which scenario to grab, 2.5 ft) and
the SFEI dasymetric population estimates (gitignored, download locally)
still need manual downloads per the planning doc. The actual El Niño-
bump-vs-neutral-winter *empirical* comparison (this used Mei's ~1 ft
figure directly, not a measured value from RONI + the historical winters)
hasn't been done -- see the project planning doc and
`docs/datum_handling.md`'s "still open" notes.
