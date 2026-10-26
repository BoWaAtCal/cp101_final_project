"""
Block groups + ACS population, for scripts/exposure_by_olu.py.

Inputs (in data/raw/census/):
    tl_2022_06_bg.zip
        TIGER/Line 2022 block-group boundaries, all of California.
        https://www2.census.gov/geo/tiger/TIGER2022/BG/tl_2022_06_bg.zip
    acs2022_b01003_bayarea_blockgroups.csv
        ACS 2018-2022 5-year table B01003 (total population) for block
        groups in the 9 Bay Area counties. Filtered from the Census
        table-based summary file (the Census API now requires a key):
        https://www2.census.gov/programs-surveys/acs/summary_file/2022/table-based-SF/data/5YRData/acsdt5y2022-b01003.dat
        Columns: GEO_ID (e.g. 1500000US060014001001), B01003_E001
        (estimate), B01003_M001 (margin of error).

ACS 2018-2022 matches the SVI vintage, so there's no year mismatch
between people and vulnerability.

Usage:
    python scripts/prep_block_groups.py

Output:
    data/processed/block_groups_bayarea.gpkg
        Bay Area block groups, EPSG:26910, with GEOID (12 digits), pop
        (ACS estimate), pop_moe (margin of error).
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw" / "census"
OUT_PATH = REPO_ROOT / "data" / "processed" / "block_groups_bayarea.gpkg"
TARGET_CRS = "EPSG:26910"

BAY_AREA_COUNTY_FIPS = ["001", "013", "041", "055", "075", "081", "085", "095", "097"]


def main():
    bg = gpd.read_file(f"zip://{RAW / 'tl_2022_06_bg.zip'}")
    bg = bg[bg["COUNTYFP"].isin(BAY_AREA_COUNTY_FIPS)][["GEOID", "COUNTYFP", "ALAND", "AWATER", "geometry"]]
    print(f"{len(bg):,} Bay Area block groups in TIGER")

    acs = pd.read_csv(RAW / "acs2022_b01003_bayarea_blockgroups.csv", dtype={"GEO_ID": str})
    acs["GEOID"] = acs["GEO_ID"].str.split("US").str[1]
    acs = acs.rename(columns={"B01003_E001": "pop", "B01003_M001": "pop_moe"})[["GEOID", "pop", "pop_moe"]]
    print(f"{len(acs):,} block groups in ACS, {acs['pop'].sum():,} people")

    out = bg.merge(acs, on="GEOID", how="left", validate="one_to_one")
    missing = out["pop"].isna().sum()
    if missing:
        print(f"WARNING: {missing} block groups have no ACS population")
    unmatched = len(set(acs["GEOID"]) - set(bg["GEOID"]))
    if unmatched:
        print(f"WARNING: {unmatched} ACS block groups have no TIGER shape")

    out = out.to_crs(TARGET_CRS)
    out.to_file(OUT_PATH, driver="GPKG")
    print(f"Wrote {OUT_PATH} ({len(out):,} block groups, {out['pop'].sum():,.0f} people)")


if __name__ == "__main__":
    main()
