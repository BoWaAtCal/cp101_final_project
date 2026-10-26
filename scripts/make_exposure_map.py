"""
Step 8 figure: map of people exposed by OLU + bar chart of the top OLUs.

Reads the output of scripts/exposure_by_olu.py, so run that first.

Usage:
    source .venv/bin/activate
    python scripts/make_exposure_map.py                  # 2.5 ft
    python scripts/make_exposure_map.py --scenario-ft 2  # any scenario you've run

Output:
    outputs/exposure_map_<scenario>.png
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
OUT_DIR = REPO_ROOT / "outputs"

# These OLUs (Carquinez + Suisun) fall outside NOAA's SF Bay file; their
# flooding is in NOAA's separate CA_Delta file. Shown hatched as "no data"
# rather than shaded as zero.
NO_COVERAGE_OLUS = [8, 9, 10, 11, 12, 13]

# Color classes for people exposed.
BINS = [0, 250, 1000, 2500, 5000, 8000, 14000]
LABEL_MIN_PEOPLE = 2000  # only label OLUs above this, to keep the map readable
TOP_N = 12


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario-ft", type=float, default=2.5)
    args = p.parse_args()
    tag = f"{args.scenario_ft:g}ft".replace(".", "_")

    olu = gpd.read_file(OUT_DIR / f"exposure_by_olu_{tag}.gpkg")
    background = gpd.read_file(PROCESSED / "svi_bayarea_tracts.gpkg").dissolve()  # 9-county outline
    no_data = olu["olu_id"].isin(NO_COVERAGE_OLUS)

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(15, 11), dpi=150,
                                 gridspec_kw=dict(width_ratios=[1.35, 1]))

    # ---- left: map
    background.plot(ax=ax, color="#f2f2f2", edgecolor="none")
    BINS[-1] = max(BINS[-1], olu["people"].max())  # make sure the top class holds the max
    cmap = plt.get_cmap("YlOrRd", len(BINS) - 1)
    norm = BoundaryNorm(BINS, cmap.N)
    olu[~no_data].plot(ax=ax, column="people", cmap=cmap, norm=norm, edgecolor="#444", lw=0.6)
    olu[no_data].plot(ax=ax, facecolor="white", edgecolor="#888", hatch="///", lw=0.6)

    for _, r in olu[olu["people"] >= LABEL_MIN_PEOPLE].iterrows():
        pt = r.geometry.representative_point()
        ax.annotate(f"{r.olu_name}\n{r.people:,.0f}", (pt.x, pt.y), fontsize=7, ha="center",
                    va="center", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))

    x0, y0, x1, y1 = olu.total_bounds
    ax.set_xlim(x0 - 5000, x1 + 5000)
    ax.set_ylim(y0 - 5000, y1 + 5000)
    ax.set_axis_off()
    fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), ax=ax, shrink=0.45, pad=0.01,
                 label=f"People exposed ({olu['pop_unit'].iloc[0]}, area-weighted)")
    ax.legend(handles=[Patch(facecolor="white", edgecolor="#888", hatch="///",
                             label="No NOAA coverage in SF Bay file\n(Suisun / Carquinez, in CA_Delta file)")],
              loc="lower left", fontsize=8)
    ax.set_title(f"People exposed at {args.scenario_ft:g} ft above MHHW, by OLU", fontsize=12)

    # ---- right: top OLUs, split into vulnerable / other
    top = olu[~no_data].sort_values("people").tail(TOP_N)
    y = np.arange(len(top))
    bx.barh(y, top["people"] - top["vuln_people"], color="#fdae6b", label="Other exposed people")
    bx.barh(y, top["vuln_people"], left=top["people"] - top["vuln_people"], color="#b30000",
            label="In high-vulnerability tracts (SVI ≥ 0.75)")
    bx.set_yticks(y, top["olu_name"])
    for i, r in enumerate(top.itertuples()):
        bx.text(r.people + 150, i, f"{r.people:,.0f}  ·  {r.road_mi:.0f} road mi  ·  {r.trail_mi:.1f} trail mi",
                va="center", fontsize=7.5)
    bx.set_xlim(0, top["people"].max() * 1.75)
    bx.set_xlabel("People exposed")
    bx.legend(loc="lower right", fontsize=8)
    bx.spines[["top", "right"]].set_visible(False)
    bx.set_title(f"Top {TOP_N} OLUs: people, roads and Bay Trail", fontsize=12)

    tot = olu[["flooded_acres", "people", "vuln_people", "road_mi", "trail_mi"]].sum()
    fig.text(0.01, 0.01,
             f"Bay-wide: {tot.flooded_acres:,.0f} acres · {tot.people:,.0f} people "
             f"({tot.vuln_people:,.0f} high-SVI) · {tot.road_mi:,.0f} road mi · {tot.trail_mi:,.0f} Bay Trail mi.  "
             "Sources: NOAA OCM SLR (ocean-connected), ACS 2018–22, CDC SVI 2022, TIGER 2025, MTC Bay Trail.",
             fontsize=8, color="#555")

    plt.tight_layout()
    out = OUT_DIR / f"exposure_map_{tag}.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
