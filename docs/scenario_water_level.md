# Scenario water level

**Method:** highest predicted King Tide this winter + 1 ft El Nino bump,
expressed as height above MHHW (the unit NOAA's SLR scenarios are
labeled in), used to pick which raster/vector file to request.

Computed by `scripts/calc_scenario_water_level.py` from the predictions
in `data/processed/tide_predictions_2026_27_navd88.csv`.

## Result

| | |
|---|---|
| Reference station | San Francisco (9414290) -- the station in the planning doc's own example query |
| Highest predicted King Tide, 2026-27 winter | **1.392 ft above MHHW**, Dec 24, 2026, 18:37 GMT |
| El Nino bump (per Mei's feedback) | +1.0 ft |
| **Scenario water level** | **2.392 ft above MHHW** |
| Nearest available NOAA SLR raster | **2.5 ft** |

## Notes

- **All 4 stations peak on the same date** (Dec 24, 2026) -- the same
  astronomical alignment drives the King Tide Bay-wide, so the date isn't
  reference-station-dependent, only the magnitude is.
- **The magnitude does vary slightly by station:** Alameda 1.327 ft,
  Richmond 1.362 ft, San Francisco 1.392 ft, Redwood City 1.410 ft. San
  Francisco was used as the single Bay-wide reference; it sits roughly in
  the middle of that range. Using Redwood City instead would give a
  2.41 ft scenario -- still closest to the same 2.5 ft raster, so the
  raster choice doesn't change, but a different reference station could
  matter for a finer-grained (per-OLU) scenario later.
- **2.39 ft rounds to the 2.5 ft raster, not 2 ft** -- it's 0.11 ft from
  2.5 vs. 0.39 ft from 2. This uses "nearest available increment"; if the
  project wants a conservative (always round up) convention instead for
  flood planning, that would also land on 2.5 ft here, so it doesn't
  change the outcome this time -- but the convention should be decided
  explicitly for future scenarios where it might.
- **This does not download or clip the NOAA SLR data itself.** It only
  identifies which scenario label (2.5 ft) to go get -- the actual file
  is the gitignored manual-download item from the planning doc.
- All values here are MHHW-referenced, matching how NOAA labels its SLR
  scenarios. See `docs/datum_handling.md` for how these same predictions
  convert to NAVD88 for comparing against the SLR data's actual elevation
  values once it's downloaded.
