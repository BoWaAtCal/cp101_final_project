# Vertical datum handling

Written in response to Mei's MTC feedback:

> "it can get tricky working with data sources of different vertical
> datums - this requires careful checking of metadata... While El Nino is
> projected to add one foot of sea level rise in the Bay, this is in
> addition to typical changes in tides."

## The problem

This project combines two kinds of water-level data that are **not**
natively in the same vertical reference frame:

1. **CO-OPS tide gauge data** (observed + predicted water levels) is
   published relative to each station's own local **tidal datum**
   (we're pulling it as MHHW, Mean Higher-High Water) -- a station-specific
   average, not a fixed elevation.
2. **NOAA SLR inundation data** is built differently: per NOAA's own
   metadata (InPort item 48106), the underlying tidal surface "represents
   the MHHW tidal datum in orthometric values (NAVD88)." In other words,
   NOAA modeled a continuous MHHW water surface across the whole mapped
   area and expressed *that* in NAVD88 -- an absolute, non-tidal elevation
   datum -- then layered the 0.5-10 ft scenarios on top of it. The actual
   raster/vector cell values are NAVD88 elevations, not "feet above MHHW"
   at any single station.

So: tide gauge readings come to us MHHW-referenced and
station-local; the inundation data we're overlaying them on is
NAVD88-referenced and Bay-wide. They have to be reconciled before any
water level from the tide gauges can be compared against the SLR data.

## Why this isn't a single Bay-wide number

The MHHW-to-NAVD88 offset is **not constant across the Bay** -- it's
specific to each tide station, because tidal range itself amplifies
moving south/inland into the estuary. Pulled directly from the CO-OPS
Datums API for our 4 stations:

| Station | MHHW - NAVD88 |
|---|---|
| San Francisco (9414290) | +5.90 ft |
| Richmond (9414863) | +6.06 ft |
| Alameda (9414750) | +6.37 ft |
| Redwood City (9414523) | +7.02 ft |

That's a >1 ft spread just among these 4 stations. Applying San
Francisco's offset to Redwood City data (or vice versa) would introduce
over a foot of error right at the step where we're trying to resolve
foot-scale flood scenarios -- exactly the kind of mistake Mei's comment is
warning about.

## What we did

Standardized everything to **NAVD88**, since that's what the NOAA SLR
data is natively expressed in -- converting SLR to MHHW-at-a-station would
be the wrong direction (one Bay-wide modeled MHHW surface vs. many local
station datums).

`scripts/fetch_tide_levels.py`:
1. Pulls each station's official MHHW and NAVD88 values from the CO-OPS
   Datums API (not hardcoded -- fetched live, so it stays correct if NOAA
   updates a station's datum epoch).
2. Pulls hourly water levels (observed + predicted) in MHHW for the 4
   stations x 4 candidate winters from the planning doc.
3. Converts every value: `water_level_navd88 = water_level_mhhw + (MHHW - NAVD88)`
   using that *station's own* offset above.

Output: `data/processed/tide_levels_navd88.csv` -- one row per
station/winter/hour, with the original MHHW value, the station's offset,
and the converted NAVD88 value kept side by side for traceability.

## Layers of water level, and where El Nino fits

Per Mei's note, the El Nino bump is **additive to normal tidal
variation**, not a replacement for it:

```
total water level (NAVD88)
  = station's observed/predicted tide at that hour (NAVD88)   <- includes the King Tide peak + normal tidal cycle
  + El Nino increment (empirically ~1 ft, per Mei's comment)   <- measured from comparing El Nino vs. neutral winters
```

The 1997-98 and 2015-16 winters in our pull are strong, well-documented
El Nino winters; 1982-83 and 2023-24 still need to be checked against the
RONI index we also pulled (`data/raw/RONI.ascii.txt`) and matched with at
least one neutral winter, to actually measure the bump empirically rather
than assume Mei's "~1 ft" figure applies uniformly at every station. That
comparison (and building the 2026-27 forward scenario) is downstream work
this note doesn't do.

Once a target water level is built this way, in NAVD88, it's directly
comparable to the NAVD88 NOAA SLR surfaces -- same reference frame on both
sides.

## Known data gaps (surfaced while pulling this)

- **San Francisco station has no verified hourly observations after
  Dec 31, 2023** (as of this data pull) -- the 2023-24 winter series is
  truncated to ~2 months instead of the full Nov-Mar window. Astronomical
  *predictions* are available for the missing period as a fallback if
  needed.
- **Richmond and Redwood City have no data for 1982-83** -- both stations'
  datum epochs were only accepted in 2020, and their period of record
  doesn't reach back that far. If 1982-83 is needed for those stations,
  it isn't available from CO-OPS directly.

## Open item: WRMP LiDAR

Mei's feedback also points to the WRMP 2025 Estuarywide LiDAR as a
higher-resolution alternative to NOAA's elevation data for a "bathtub"
approach. We have **not** downloaded or vetted this dataset -- it isn't
in the repo, and WRMP's public project page doesn't state its vertical
datum. If this gets adopted later, its datum needs to be confirmed from
the actual data's metadata (not assumed to be NAVD88) before combining it
with anything in this document.

## Still in MHHW / not yet reconciled

- **TIGER roads and CDC SVI are horizontally reprojected to EPSG:26910
  but have no vertical component** -- not relevant for this note (no
  elevation data there), noted only so it's clear "all layers on one
  datum" refers to the water-level sources, not every dataset in the repo.
- **NOAA SLR depth rasters/vectors themselves are not yet downloaded**
  (gitignored per the project doc, ~download locally). Once downloaded,
  no further datum conversion should be needed -- they're already NAVD88
  per NOAA's metadata above -- but that should be spot-checked against the
  file's own metadata when it's in hand, not assumed from this note alone.
