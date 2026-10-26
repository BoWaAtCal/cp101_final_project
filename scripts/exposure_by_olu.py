"""
Step 6: exposure analysis -- overlay the inundation layer on population,
roads, and the Bay Trail, and total everything by OLU into one table.

Usage:
    source .venv/bin/activate
    python scripts/exposure_by_olu.py                 # 2.5 ft (step 5's pick)
    python scripts/exposure_by_olu.py --scenario-ft 2 # any other NOAA layer

Inputs:
    data/CA_SFBay_slr_final_dist.gpkg      NOAA SLR vectors (gitignored, download
                                           manually -- see the planning doc)
    data/processed/olu_primary.gpkg        the 30 OLUs (join skeleton)
    data/processed/block_groups_bayarea.gpkg
                                           block groups with a population column
                                           (see POPULATION below)
    data/processed/svi_bayarea_tracts.gpkg SVI percentile, for "vulnerable" flag
    data/processed/roads_bayarea.gpkg      TIGER roads
    data/processed/bay_trail.gpkg          Bay Trail

Outputs:
    outputs/exposure_by_olu_<scenario>.csv   one row per OLU, one column per metric
    outputs/exposure_by_olu_<scenario>.gpkg  same table joined to OLU polygons (for maps)

FLOOD LAYER
    NOAA's file has one layer per scenario. Layers containing "_slr_" are the
    ocean-connected inundation; layers containing "_low_" are unconnected
    low-lying areas that *may* flood. This uses the "_slr_" layer only by
    default; pass --include-low to add the low-lying areas.

POPULATION (midterm method, per the planning doc)
    Area-weighted: each block group's population is spread evenly over its
    area, so a block group that is 20% flooded contributes 20% of its people.
    This overcounts where block groups include marsh/parks/industrial land;
    step 11 replaces it with SFEI's dasymetric building-level estimates.

    The block-group file isn't in the repo yet. It needs a 12-digit `GEOID`
    column and a population column (default `pop`, e.g. ACS B01003_001E).
    If it's missing, the script falls back to SVI tracts (E_TOTPOP) and
    says so in the `pop_unit` output column -- coarser, same method.

    "Vulnerable people exposed" = exposed people living in a tract with SVI
    RPL_THEMES >= 0.75 (block groups inherit their parent tract's score via
    the first 11 GEOID digits). SVI's -999 "no data" is treated as missing.
    Vintage mismatch: SVI is 2018-2022 ACS; note whichever ACS year the block
    groups come from.
"""

import argparse
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
PROCESSED = DATA / "processed"
OUT_DIR = REPO_ROOT / "outputs"
TARGET_CRS = "EPSG:26910"

M2_PER_ACRE = 4046.8564224
M_PER_MILE = 1609.344
SVI_HIGH = 0.75
# TIGER MTFCC codes for primary roads (S1100) and secondary roads (S1200)
MAJOR_ROAD_CODES = {"S1100", "S1200"}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--scenario-ft", type=float, default=2.5,
                   help="NOAA SLR scenario in ft above MHHW (default 2.5, from docs/scenario_water_level.md)")
    p.add_argument("--slr-gpkg", type=Path, default=DATA / "CA_SFBay_slr_final_dist.gpkg")
    p.add_argument("--include-low", action="store_true",
                   help="also count NOAA's unconnected low-lying areas as flooded")
    p.add_argument("--block-groups", type=Path, default=PROCESSED / "block_groups_bayarea.gpkg")
    p.add_argument("--pop-col", default="pop", help="population column in the block-group file")
    return p.parse_args()


# ---------------------------------------------------------------- flood layer

def find_layer(layers, kind, scenario_ft):
    """Return the NOAA layer name for e.g. kind='slr', 2.5 ft (named like '..._slr_2_5ft')."""
    for name in layers:
        m = re.search(rf"_{kind}_(\d+)(?:[_.](\d+))?ft", name, re.IGNORECASE)
        if m and float(f"{m.group(1)}.{m.group(2) or 0}") == scenario_ft:
            return name
    return None


def load_flood(args, olu):
    if not args.slr_gpkg.exists():
        raise FileNotFoundError(
            f"{args.slr_gpkg} not found. It's gitignored -- download the CA SFBay SLR "
            "vectors per the planning doc and put it in data/.")
    layers = list(pyogrio.list_layers(args.slr_gpkg)[:, 0])
    wanted = [find_layer(layers, "slr", args.scenario_ft)]
    if args.include_low:
        wanted.append(find_layer(layers, "low", args.scenario_ft))
    if None in wanted:
        raise ValueError(f"No {args.scenario_ft} ft layer found. Layers in the file: {layers}")

    frames = []
    for name in wanted:
        layer_crs = pyogrio.read_info(args.slr_gpkg, layer=name)["crs"]
        bbox = tuple(olu.to_crs(layer_crs).total_bounds)  # only read what can touch an OLU
        gdf = gpd.read_file(args.slr_gpkg, layer=name, bbox=bbox)
        print(f"  {name}: {len(gdf):,} polygons")
        frames.append(gdf.to_crs(TARGET_CRS)[["geometry"]])
    flood = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=TARGET_CRS)
    flood["geometry"] = shapely.make_valid(flood.geometry.values)
    flood = flood[flood.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"])]

    # One flood polygon per OLU. Dissolving first means overlapping NOAA
    # polygons (or slr + low) are never counted twice.
    flood_olu = gpd.overlay(flood, olu[["olu_id", "geometry"]], how="intersection", keep_geom_type=True)
    flood_olu = flood_olu.dissolve(by="olu_id").reset_index()
    return flood_olu[["olu_id", "geometry"]]


# ---------------------------------------------------------------- population

def load_population(args, svi):
    svi = svi.copy()
    svi["svi"] = svi["RPL_THEMES"].where(svi["RPL_THEMES"] >= 0)  # -999 -> NaN

    if args.block_groups.exists():
        bg = gpd.read_file(args.block_groups).to_crs(TARGET_CRS)
        if args.pop_col not in bg.columns:
            raise KeyError(f"'{args.pop_col}' not in {args.block_groups}: {list(bg.columns)}")
        bg["GEOID"] = bg["GEOID"].astype(str).str.zfill(12)
        bg = bg.merge(svi[["FIPS", "svi"]], left_on=bg["GEOID"].str[:11], right_on="FIPS", how="left")
        pop = bg.rename(columns={args.pop_col: "pop"})[["GEOID", "pop", "svi", "geometry"]]
        unit = "block group"
    else:
        print(f"  WARNING: {args.block_groups} not found -- falling back to SVI tracts (E_TOTPOP).")
        pop = svi.rename(columns={"FIPS": "GEOID", "E_TOTPOP": "pop"})[["GEOID", "pop", "svi", "geometry"]]
        unit = "tract"

    pop = gpd.GeoDataFrame(pop, geometry="geometry", crs=TARGET_CRS)
    pop["unit_area"] = pop.area
    print(f"  {len(pop):,} {unit}s, {pop['pop'].sum():,.0f} people, "
          f"{pop['svi'].isna().sum()} with no SVI score")
    return pop, unit


def area_weighted_people(pop, polys, prefix):
    """Spread each unit's population evenly over its area, total it within `polys` by OLU."""
    pieces = gpd.overlay(pop, polys, how="intersection", keep_geom_type=True)
    pieces["people"] = pieces["pop"] * pieces.area / pieces["unit_area"]
    pieces["vuln_people"] = pieces["people"].where(pieces["svi"] >= SVI_HIGH, 0.0)
    return pieces.groupby("olu_id").agg(
        **{f"{prefix}people": ("people", "sum"), f"{prefix}vuln_people": ("vuln_people", "sum")})


# ---------------------------------------------------------------- lines

def clip_lines(lines, polys):
    """Pieces of `lines` inside `polys`, tagged with olu_id. One row per line x OLU."""
    hits = gpd.sjoin(lines, polys[["olu_id", "geometry"]], predicate="intersects", how="inner")
    clip_geoms = polys.set_index("olu_id").geometry.loc[hits["olu_id"]].values
    hits = hits.drop(columns="index_right").copy()
    hits["geometry"] = shapely.intersection(hits.geometry.values, clip_geoms)
    hits = hits[~hits.geometry.is_empty]
    hits["clip_mi"] = hits.geometry.length / M_PER_MILE
    return hits


def road_miles(roads, polys, prefix):
    r = clip_lines(roads, polys)
    r["major_mi"] = r["clip_mi"].where(r["MTFCC"].isin(MAJOR_ROAD_CODES), 0.0)
    return r.groupby("olu_id").agg(
        **{f"{prefix}road_mi": ("clip_mi", "sum"), f"{prefix}major_road_mi": ("major_mi", "sum")})


def trail_miles(trail, polys, prefix):
    t = clip_lines(trail, polys)
    # Planning-doc quirk: segment 4032 used to appear twice in the service.
    # fetch_bay_trail.py found no duplicates in the source; re-check after the
    # join, since a duplicated *row* would show up here as the same segment
    # twice within one OLU (straddling two OLUs is fine -- different pieces).
    dupes = t.duplicated(subset=["segment_nu", "olu_id"])
    if dupes.any():
        print(f"  WARNING: dropping {dupes.sum()} duplicated trail segment rows: "
              f"{sorted(t.loc[dupes, 'segment_nu'].unique())}")
        t = t[~dupes]
    return t.groupby("olu_id").agg(
        **{f"{prefix}trail_mi": ("clip_mi", "sum"), f"{prefix}trail_segments": ("segment_nu", "nunique")})


# ---------------------------------------------------------------- main

def main():
    args = parse_args()
    tag = f"{args.scenario_ft:g}ft".replace(".", "_") + ("_with_low" if args.include_low else "")
    OUT_DIR.mkdir(exist_ok=True)

    print("Loading layers")
    olu = gpd.read_file(PROCESSED / "olu_primary.gpkg")[["olu_id", "olu_name", "geometry"]]
    svi = gpd.read_file(PROCESSED / "svi_bayarea_tracts.gpkg")
    roads = gpd.read_file(PROCESSED / "roads_bayarea.gpkg")
    trail = gpd.read_file(PROCESSED / "bay_trail.gpkg")
    pop, unit = load_population(args, svi)

    print(f"Building the {args.scenario_ft:g} ft flood extent by OLU")
    flood = load_flood(args, olu)

    print("Overlaying")
    table = olu[["olu_id", "olu_name"]].set_index("olu_id")
    table["olu_acres"] = olu.set_index("olu_id").area / M2_PER_ACRE
    table["flooded_acres"] = flood.set_index("olu_id").area / M2_PER_ACRE
    # Totals for the whole OLU (denominators), then the flooded part.
    for polys, prefix in [(olu, "olu_"), (flood, "")]:
        table = table.join(area_weighted_people(pop, polys, prefix))
        table = table.join(road_miles(roads, polys, prefix))
        table = table.join(trail_miles(trail, polys, prefix))

    table = table.fillna(0.0)
    table["pct_flooded"] = 100 * table["flooded_acres"] / table["olu_acres"]
    table["pct_people_exposed"] = 100 * table["people"] / table["olu_people"].replace(0, np.nan)
    table["pct_road_flooded"] = 100 * table["road_mi"] / table["olu_road_mi"].replace(0, np.nan)
    table["pct_trail_flooded"] = 100 * table["trail_mi"] / table["olu_trail_mi"].replace(0, np.nan)
    table["scenario_ft"] = args.scenario_ft
    table["pop_unit"] = unit

    cols = ["olu_name", "scenario_ft",
            "flooded_acres", "pct_flooded",
            "people", "vuln_people", "pct_people_exposed",
            "road_mi", "major_road_mi", "pct_road_flooded",
            "trail_mi", "trail_segments", "pct_trail_flooded",
            "olu_acres", "olu_people", "olu_vuln_people", "olu_road_mi", "olu_major_road_mi",
            "olu_trail_mi", "olu_trail_segments", "pop_unit"]
    table = table[cols].sort_values("people", ascending=False).round(2)

    csv_path = OUT_DIR / f"exposure_by_olu_{tag}.csv"
    table.to_csv(csv_path)
    olu.drop(columns="olu_name").merge(table.reset_index(), on="olu_id").to_file(
        OUT_DIR / f"exposure_by_olu_{tag}.gpkg", driver="GPKG")

    print(f"\nWrote {csv_path}")
    total = table[["flooded_acres", "people", "vuln_people", "road_mi", "trail_mi"]].sum()
    print(f"Bay-wide: {total.flooded_acres:,.0f} acres, {total.people:,.0f} people "
          f"({total.vuln_people:,.0f} in high-SVI {unit}s), {total.road_mi:,.1f} road mi, "
          f"{total.trail_mi:,.1f} Bay Trail mi")
    print("\nTop 10 OLUs by people exposed:")
    print(table.head(10)[["olu_name", "flooded_acres", "people", "vuln_people", "road_mi", "trail_mi"]]
          .to_string())


if __name__ == "__main__":
    main()
