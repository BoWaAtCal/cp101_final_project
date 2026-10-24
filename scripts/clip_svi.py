"""
Step 5 (light touch): CDC SVI, clipped to the 9 Bay Area counties.

The committed data/SVI2022_CALIFORNIA_tract.gdb is the FULL California file
(9,109 tracts, all 58 counties). The project doc calls for the file clipped
to the 9 Bay Area counties. This just filters by county FIPS (STCNTY) --
no spatial clipping needed since tracts already nest within counties.

NOTE: this script does NOT do the SFEI dasymetric population join or the
flood-overlay work described in the project doc (those depend on steps
1-3, which aren't built yet). It only produces the clean, Bay-Area-only
SVI layer the doc asks for as a starting point.

Usage:
    source .venv/bin/activate
    python scripts/clip_svi.py

Output:
    data/processed/svi_bayarea_tracts.gpkg
        SVI 2022 tracts for the 9 Bay Area counties only, reprojected to
        EPSG:26910 to match data/processed/olu_primary.gpkg. Key columns:
          - STCNTY / COUNTY: county FIPS / name
          - E_TOTPOP: total population (tract-level estimate)
          - RPL_THEMES: overall SVI percentile rank, 0-1 (higher = more
            vulnerable). This is the score the doc suggests thresholding
            at >= 0.75 to flag "vulnerable people exposed."
          - RPL_THEME1-4: the four vulnerability sub-themes (socioeconomic,
            household composition, racial/ethnic minority status &
            language, housing type & transportation)

CAVEAT (per the planning doc): SVI vintage is 2018-2022 ACS, while the
SFEI dasymetric population dataset (not yet downloaded -- it's gitignored,
~1GB) is 2017-2021 ACS. Note this mismatch wherever these are combined.
"""

from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parent.parent
SVI_GDB = REPO_ROOT / "data" / "SVI2022_CALIFORNIA_tract.gdb"
OUT_PATH = REPO_ROOT / "data" / "processed" / "svi_bayarea_tracts.gpkg"
TARGET_CRS = "EPSG:26910"  # match data/processed/olu_primary.gpkg

# Per the project doc.
BAY_AREA_COUNTY_FIPS = {
    "06001": "Alameda",
    "06013": "Contra Costa",
    "06041": "Marin",
    "06055": "Napa",
    "06075": "San Francisco",
    "06081": "San Mateo",
    "06085": "Santa Clara",
    "06095": "Solano",
    "06097": "Sonoma",
}


def main():
    if not SVI_GDB.exists():
        raise FileNotFoundError(f"Expected {SVI_GDB} — pull latest from git first.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    svi = gpd.read_file(SVI_GDB, layer="SVI2022_CALIFORNIA_tract")
    print(f"Loaded {len(svi)} California tracts")

    bay = svi[svi["STCNTY"].isin(BAY_AREA_COUNTY_FIPS)].copy()
    bay = bay.to_crs(TARGET_CRS)

    bay.to_file(OUT_PATH, driver="GPKG")
    print(f"Wrote {OUT_PATH} ({len(bay)} tracts)")

    print("\nTracts per county:")
    counts = bay["COUNTY"].value_counts().sort_index()
    for county, n in counts.items():
        print(f"  {county:<15} {n}")

    missing = set(BAY_AREA_COUNTY_FIPS) - set(bay["STCNTY"].unique())
    if missing:
        print(f"\nWARNING: no tracts found for FIPS {missing}")


if __name__ == "__main__":
    main()
