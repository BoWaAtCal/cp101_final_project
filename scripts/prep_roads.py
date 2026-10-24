"""
Roads: clip-to-Bay + common CRS.

The 9 TIGER county road files are already "clipped to the Bay Area" in the
sense that each one is bounded by its county -- the 9 counties together
*are* the Bay Area boundary used elsewhere in this project (same as
scripts/clip_svi.py). This script just merges them into one layer and
reprojects to the project's common CRS.

Usage:
    source .venv/bin/activate
    python scripts/prep_roads.py

Output:
    data/processed/roads_bayarea.gpkg -- all 9 counties' roads combined,
    EPSG:26910, with a `county_fips` column added.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
ROADS_DIR = REPO_ROOT / "data" / "Roads"
OUT_PATH = REPO_ROOT / "data" / "processed" / "roads_bayarea.gpkg"
TARGET_CRS = "EPSG:26910"

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
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    frames = []
    for fips, county_name in BAY_AREA_COUNTY_FIPS.items():
        zip_path = ROADS_DIR / f"tl_2025_{fips}_roads.zip"
        if not zip_path.exists():
            raise FileNotFoundError(f"Missing {zip_path}")
        gdf = gpd.read_file(f"zip://{zip_path}")
        gdf["county_fips"] = fips
        gdf["county_name"] = county_name
        frames.append(gdf)
        print(f"  {county_name:<15} {len(gdf)} road segments")

    roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    roads = roads.to_crs(TARGET_CRS)
    roads["length_mi"] = roads.geometry.length / 1609.344

    roads.to_file(OUT_PATH, driver="GPKG")
    print(f"\nWrote {OUT_PATH} ({len(roads)} segments, {roads['length_mi'].sum():,.0f} mi total)")


if __name__ == "__main__":
    main()
