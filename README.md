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
python scripts/calc_scenario_water_level.py
python scripts/exposure_by_olu.py
python scripts/make_exposure_map.py
python scripts/run_historical_analysis.py
python scripts/visualize_historical_analysis.py
```

The NOAA / MTC download scripts (`fetch_tide_levels.py`,
`fetch_2026_27_predictions.py`, `fetch_bay_trail.py`) are optional: their
outputs are already saved in `data/raw/` and `data/processed/`, and
re-running them needs internet access and overwrites those files with
whatever the APIs return today.

`run_historical_analysis.py` compares each historical El Niño winter
(1982-83, 1997-98, 2015-16) against the nearest preceding ENSO-neutral
winter (all of NDJ, DJF, JFM RONI within ±0.5) at the same station, and
writes the CSVs that `visualize_historical_analysis.py` plots. The neutral
winters' tide data (1981-82, 1996-97, 2013-14) are saved in
`data/raw/tide_levels/`, so it runs offline.

### Where the data comes from

| File in `data/` | Source | How to get it |
|---|---|---|
| `CA_SFBay_slr_final_dist.gpkg` (gitignored) | NOAA OCM Sea Level Rise inundation vectors, San Francisco Bay | Manual download from https://coast.noaa.gov/slrdata/ (California → SF Bay, vector GeoPackage); metadata in `data/NOAA_OCM_SLR_Data_README.txt` |
| `Bay_Area_Dasymetric_Population_Estimates.gpkg` (gitignored) | SFEI dasymetric population | Manual download per the project doc; not used by the current scripts |
| `Adaptation_Atlas_Data_SFEI_v3_2021.mpk` | SFEI Adaptation Atlas (OLUs) | Committed; from http://www.sfei.org/data/adaptation-atlas-data |
| `SVI2022_CALIFORNIA_tract.gdb` | CDC/ATSDR Social Vulnerability Index 2022, California tracts | Committed; from https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html |
| `Roads/tl_2025_<county>_roads.zip` | Census TIGER/Line 2025 roads, 9 counties | Committed; from https://www2.census.gov/geo/tiger/TIGER2025/ROADS/ |
| `raw/census/` | TIGER 2022 block groups + ACS 2018-22 table B01003 | Committed; URLs in `scripts/prep_block_groups.py` |
| `raw/tide_levels/`, `raw/RONI.ascii.txt` | NOAA CO-OPS API, NOAA CPC | Downloaded by `fetch_tide_levels.py`, `fetch_2026_27_predictions.py`, `run_historical_analysis.py` |
| `raw/bay_trail.geojson` | MTC Bay Trail feature service | Downloaded by `fetch_bay_trail.py` |

## Data cleaning

Every step that removes, filters or fixes rows, with the counts from a
full run. The scripts print these counts when they run.

| Step | Script | What was done | Rows before → after | Rows affected |
|---|---|---|---|---|
| OLUs | `data_processing.py` | Kept only the `Primary` component (dropped `Submerged` and `Contributing watershed`) | 89 → 30 | 59 removed |
| SVI tracts | `data_processing.py` | Kept the 9 Bay Area counties (by `STCNTY` FIPS) | 9,109 → 1,765 | 7,344 removed |
| SVI scores | `exposure_by_olu.py` | `RPL_THEMES` = -999 ("no data") set to missing, so it isn't read as a real score | 1,765 | 9 tracts fixed |
| Block groups | `prep_block_groups.py` | Kept the 9 Bay Area counties (by `COUNTYFP`) | 25,607 → 5,187 | 20,420 removed |
| Block-group population | `prep_block_groups.py` | Joined ACS population to block-group shapes | 5,187 | 0 unmatched in either direction |
| Block-group SVI | `exposure_by_olu.py` | Joined tract SVI to block groups; no score = never counted as high-vulnerability | 5,187 | 16 with no SVI score |
| Roads | `data_processing.py` | Merged 9 county files, reprojected; nothing removed | 151,426 → 151,426 | 0 |
| Bay Trail | `fetch_bay_trail.py`, `exposure_by_olu.py` | Checked for the known segment-4032 duplicate in the source and again after the OLU join | 683 → 683 | 0 duplicates |
| NOAA flood polygons (2.5 ft) | `exposure_by_olu.py` | Repaired invalid geometries, dropped non-polygon pieces | 1,523 → 1,523 | 0 |
| Tide observations | `fetch_tide_levels.py` | Dropped hours with a blank water level | 48,744 → 48,744 | 0 blank hours |
| Tide observations | `fetch_tide_levels.py` | Station-winters NOAA has no data for | 16 → 14 | 2 missing (Richmond and Redwood City 1982-83) |
| Tide predictions | `fetch_2026_27_predictions.py` | Dropped blank predictions | 2,332 → 2,332 | 0 |
| Neutral-winter tides | `run_historical_analysis.py` | Dropped blank hours; skipped station pairs with no data | Alameda 1996-97: 3,623 → 3,456 | 167 blank hours; 3 station comparisons skipped |
| All layers | all scripts | Reprojected to EPSG:26910; water levels converted MHHW → NAVD88 per station (`docs/datum_handling.md`) | — | values changed, no rows removed |

Known gap kept as-is: San Francisco 2023-24 has only 1,464 hourly
observations (Nov-Dec 2023), versus about 3,648 for a full winter, because
NOAA has no verified data after Dec 31, 2023.

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

One map and five charts, each with a one-sentence caption:

| Figure | Caption |
|---|---|
| `exposure_map_2_5ft.png`, left (map) | People living in the 2.5 ft-above-MHHW flood extent in each OLU, area-weighted from block groups (Suisun and Carquinez hatched: no NOAA SF Bay coverage). |
| `exposure_map_2_5ft.png`, right (bar chart) | The 12 OLUs with the most people exposed at 2.5 ft, split into people in high-vulnerability tracts (SVI ≥ 0.75) and everyone else, with flooded road and Bay Trail miles. |
| `historical_analysis/el_nino_historical_visualizations.png`, A | How much higher the 95th-percentile and maximum hourly water levels (ft) were in three past El Niño winters than in the nearest neutral winter, against our +1 ft assumption. |
| same, B | Winter El Niño strength (RONI) against the 95th-percentile high-water anomaly (ft) for the three events, which is descriptive only with n = 3. |
| same, C | Monthly maximum predicted astronomical high tide (ft above MHHW) at the four stations for Nov 2026-Mar 2027, peaking in December. |
| same, D | The 10 OLUs with the most people exposed under the 2.5 ft scenario. |

More detail:

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

Population is still area-weighted by block group; swapping in the SFEI
dasymetric estimates (gitignored, download locally) is step 11. The
exposure scenario still uses Mei's ~1 ft El Niño figure directly. The
historical comparison (`run_historical_analysis.py`) measured 0.27-0.69 ft
at the 95th percentile, so that assumption is not yet replaced by a
measured value -- see `docs/datum_handling.md`'s "still open" notes.
