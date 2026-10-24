"""
Step 4: Operational Landscape Units (OLUs)

Extracts the OLU polygons from the SFEI Adaptation Atlas .mpk (an Esri Map
Package, which is a 7-zip archive containing one or more File Geodatabases)
and writes clean, analysis-ready GeoPackages to data/processed/.

Why this script exists: the .mpk can't be opened directly with
geopandas/fiona, and most of us don't have ArcGIS. This avoids needing it.

Usage:
    source .venv/bin/activate
    python scripts/extract_olu.py

Outputs:
    data/processed/olu_primary.gpkg
        30 rows, one per OLU (the "Primary" component: shoreline + the land
        behind it). THIS is the layer to use as the join skeleton for
        ranking -- intersect flood polygons / SVI tracts / roads / Bay Trail
        against this to get per-OLU totals.
    data/processed/olu_all_components.gpkg
        All 89 rows, all 3 component types per OLU (Primary, Submerged,
        Contributing watershed), kept in case the watershed or submerged
        extents are needed for anything (e.g. full catchment analysis).

Both outputs are reprojected to EPSG:26910 (UTM Zone 10N, meters), a good
common CRS for Bay Area distance/area work. The SVI and TIGER roads layers
in this repo are EPSG:4269; reproject them to EPSG:26910 too before any
spatial join / area or length calculation so units come out in meters.

Source: San Francisco Estuary Institute (SFEI). 2019. "San Francisco Bay
Shoreline Adaptation Atlas GIS data, Version 3."
http://www.sfei.org/data/adaptation-atlas-data
"""

import shutil
import tempfile
from pathlib import Path

import geopandas as gpd
import py7zr

REPO_ROOT = Path(__file__).resolve().parent.parent
MPK_PATH = REPO_ROOT / "data" / "Adaptation_Atlas_Data_SFEI_v3_2021.mpk"
OUT_DIR = REPO_ROOT / "data" / "processed"
TARGET_CRS = "EPSG:26910"  # UTM Zone 10N, meters

GDB_ENTRY_PREFIX = "v10/operational_landscape_units.gdb/"
GDB_LAYER_NAME = "OLUs_v1r1"


def extract_olu_gdb(tmp_dir: Path) -> Path:
    """Pull just the OLU geodatabase out of the .mpk archive."""
    with py7zr.SevenZipFile(MPK_PATH, mode="r") as archive:
        targets = [n for n in archive.getnames() if n.startswith(GDB_ENTRY_PREFIX)]
        if not targets:
            raise RuntimeError(
                f"Could not find {GDB_ENTRY_PREFIX} inside {MPK_PATH.name}. "
                "Has the .mpk file changed?"
            )
        archive.extract(path=tmp_dir, targets=targets)
    return tmp_dir / "v10" / "operational_landscape_units.gdb"


def main():
    if not MPK_PATH.exists():
        raise FileNotFoundError(f"Expected {MPK_PATH} — pull latest from git first.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        gdb_path = extract_olu_gdb(Path(tmp))
        olu = gpd.read_file(gdb_path, layer=GDB_LAYER_NAME)

        assert len(olu) == 89, f"Expected 89 rows (30 OLUs x 3 components), got {len(olu)}"
        assert olu["OLU_ID"].nunique() == 30, "Expected 30 unique OLUs"

        olu = olu.to_crs(TARGET_CRS)
        olu = olu.rename(
            columns={
                "OLU_ID": "olu_id",
                "OLU_Name": "olu_name",
                "OLU_Component_Type": "component_type",
            }
        )

        # All components, for reference.
        all_path = OUT_DIR / "olu_all_components.gpkg"
        olu.to_file(all_path, driver="GPKG")
        print(f"Wrote {all_path} ({len(olu)} rows)")

        # The join skeleton: one polygon per OLU (shoreline + land behind it).
        primary = olu[olu["component_type"] == "Primary"].drop(columns=["component_type"])
        primary = primary.sort_values("olu_id").reset_index(drop=True)
        primary["area_acres"] = primary.geometry.area / 4046.8564224

        primary_path = OUT_DIR / "olu_primary.gpkg"
        primary.to_file(primary_path, driver="GPKG")
        print(f"Wrote {primary_path} ({len(primary)} rows)")

        print("\nOLUs:")
        for _, row in primary.iterrows():
            print(f"  {row['olu_id']:>2}  {row['olu_name']}")


if __name__ == "__main__":
    main()
