"""
Step 7: Bay Trail (MTC feature service).

Usage:
    source .venv/bin/activate
    python scripts/fetch_bay_trail.py

Outputs:
    data/raw/bay_trail.geojson                  -- as downloaded (WGS84),
        matching the filename the planning doc specifies
    data/processed/bay_trail.gpkg                -- reprojected to
        EPSG:26910 to match the other processed layers, with a
        `length_mi` column computed from the projected geometry

KNOWN QUIRK (per the planning doc): segment 4032 was previously duplicated
in this service, which would double-count it in a spatial join -- the doc
says to delete the extra row manually. As of this pull, `segment_nu` has
no duplicates at all (683 unique values for 683 features) -- see the
printed check below. Two possibilities, not resolved here:
  1. MTC has since cleaned up the service and the duplicate is gone.
  2. The duplication only shows up AFTER intersecting with the OLU
     polygons (segment 4032's geometry straddles two OLUs, producing two
     output rows from the spatial join, not two input rows).
Whoever does the OLU x Bay Trail join should re-check for segment 4032
duplication in THAT join's output, not assume this script already
resolved it.

The service caps responses at 2,000 records; this layer has 683, well
under that, so no pagination is implemented here. If a future pull comes
back with exactly 2,000 features, that cap has likely been hit and
pagination (resultOffset/resultRecordCount) would be needed.
"""

import json
import urllib.request
from collections import Counter
from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "data" / "raw" / "bay_trail.geojson"
PROCESSED_PATH = REPO_ROOT / "data" / "processed" / "bay_trail.gpkg"
TARGET_CRS = "EPSG:26910"

QUERY_URL = (
    "https://services3.arcgis.com/i2dkYWmb4wHvYPda/ArcGIS/rest/services/"
    "bay_trail/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson"
)


def main():
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {QUERY_URL}")
    with urllib.request.urlopen(QUERY_URL, timeout=30) as r:
        raw_bytes = r.read()
    RAW_PATH.write_bytes(raw_bytes)

    gj = json.loads(raw_bytes)
    n = len(gj["features"])
    print(f"Wrote {RAW_PATH} ({n} features)")

    if n >= 2000:
        print("WARNING: response has >= 2000 features -- the service's per-request "
              "cap may have been hit. Pagination is needed; this script doesn't do it.")

    seg_counts = Counter(f["properties"].get("segment_nu") for f in gj["features"])
    dupes = {k: v for k, v in seg_counts.items() if v > 1}
    if dupes:
        print(f"Found duplicate segment_nu values in the source data: {dupes}")
    else:
        print("No duplicate segment_nu values in the source data "
              "(the doc's segment-4032 quirk may show up after the OLU join instead -- see module docstring).")

    trail = gpd.read_file(RAW_PATH)
    trail = trail.to_crs(TARGET_CRS)
    trail["length_mi"] = trail.geometry.length / 1609.344

    trail.to_file(PROCESSED_PATH, driver="GPKG")
    print(f"Wrote {PROCESSED_PATH} ({len(trail)} segments, {trail['length_mi'].sum():,.1f} mi total)")


if __name__ == "__main__":
    main()
