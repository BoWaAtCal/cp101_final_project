"""
data_processing.py: all data cleaning for the midterm, in one file.

Runs top to bottom. Combines the cleaning steps from:
  scripts/extract_olu.py  -> data/processed/olu_primary.gpkg
                             data/processed/olu_all_components.gpkg
  scripts/clip_svi.py     -> data/processed/svi_bayarea_tracts.gpkg
  scripts/prep_roads.py   -> data/processed/roads_bayarea.gpkg

Every output is reprojected to EPSG:26910 (UTM Zone 10N, meters) so areas
and lengths come out in real units and all layers line up.

Usage (from the repo root):
    python data_processing.py
"""

import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import py7zr


REPO_ROOT = Path(__file__).resolve().parent
DATA = REPO_ROOT / "data"
OUT_DIR = DATA / "processed"
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

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------Get OLUs (Operational Landscape Units)----------------------------------------------------------------

print("1. Operational Landscape Units")
MPK_PATH = DATA / "Adaptation_Atlas_Data_SFEI_v3_2021.mpk"
GDB_ENTRY_PREFIX = "v10/operational_landscape_units.gdb/"

if not MPK_PATH.exists():
    raise FileNotFoundError(f"Expected {MPK_PATH} - pull latest from git first.")

with tempfile.TemporaryDirectory() as tmp:
    with py7zr.SevenZipFile(MPK_PATH, mode="r") as archive:
        targets = [n for n in archive.getnames() if n.startswith(GDB_ENTRY_PREFIX)]
        if not targets:
            raise RuntimeError(f"Could not find {GDB_ENTRY_PREFIX} inside {MPK_PATH.name}.")
        archive.extract(path=tmp, targets=targets)
    olu = gpd.read_file(Path(tmp) / "v10" / "operational_landscape_units.gdb",
                        layer="OLUs_v1r1")

assert len(olu) == 89, f"Expected 89 rows (30 OLUs x 3 components), got {len(olu)}"
assert olu["OLU_ID"].nunique() == 30, "Expected 30 unique OLUs"

olu = olu.to_crs(TARGET_CRS)
olu = olu.rename(columns={
    "OLU_ID": "olu_id",
    "OLU_Name": "olu_name",
    "OLU_Component_Type": "component_type",
})

# All 3 components per OLU (Primary, Submerged, Contributing watershed)
olu.to_file(OUT_DIR / "olu_all_components.gpkg", driver="GPKG")
print(f"   olu_all_components.gpkg: {len(olu)} rows")

# Primary component only = one polygon per OLU, used as the join skeleton
primary = olu[olu["component_type"] == "Primary"].drop(columns=["component_type"])
primary = primary.sort_values("olu_id").reset_index(drop=True)
primary["area_acres"] = primary.geometry.area / 4046.8564224
primary.to_file(OUT_DIR / "olu_primary.gpkg", driver="GPKG")
print(f"   olu_primary.gpkg: {len(primary)} OLUs")


# ----------------------------------------------------------------Get SVI Data (Social Vulnerability Index, CDC)----------------------------------------------------------------

print("2. CDC Social Vulnerability Index")
SVI_GDB = DATA / "SVI2022_CALIFORNIA_tract.gdb"

if not SVI_GDB.exists():
    raise FileNotFoundError(f"Expected {SVI_GDB} - pull latest from git first.")

svi = gpd.read_file(SVI_GDB, layer="SVI2022_CALIFORNIA_tract")
bay_svi = svi[svi["STCNTY"].isin(BAY_AREA_COUNTY_FIPS)].copy()
bay_svi = bay_svi.to_crs(TARGET_CRS)
bay_svi.to_file(OUT_DIR / "svi_bayarea_tracts.gpkg", driver="GPKG")
print(f"   svi_bayarea_tracts.gpkg: {len(svi):,} CA tracts -> {len(bay_svi):,} Bay Area tracts")

missing = set(BAY_AREA_COUNTY_FIPS) - set(bay_svi["STCNTY"].unique())
if missing:
    print(f"   WARNING: no tracts found for FIPS {missing}")


# ----------------------------------------------------------------Get Roads----------------------------------------------------------------

print("3. TIGER roads")
ROADS_DIR = DATA / "Roads"

frames = []
for fips, county_name in BAY_AREA_COUNTY_FIPS.items():
    zip_path = ROADS_DIR / f"tl_2025_{fips}_roads.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing {zip_path}")
    gdf = gpd.read_file(f"zip://{zip_path}")
    gdf["county_fips"] = fips
    gdf["county_name"] = county_name
    frames.append(gdf)

roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
roads = roads.to_crs(TARGET_CRS)
roads["length_mi"] = roads.geometry.length / 1609.344
roads.to_file(OUT_DIR / "roads_bayarea.gpkg", driver="GPKG")
print(f"roads_bayarea.gpkg: {len(roads):,} segments, {roads['length_mi'].sum():,.0f} mi")


print(f"\nLayers written to {OUT_DIR} in {TARGET_CRS}.")