"""
Step 5: scenario water level.

Takes the highest predicted King Tide this winter (2026-27) at the
reference station, adds the 1 ft El Nino bump (per Mei's MTC feedback),
and expresses the result as height above MHHW -- the units NOAA's SLR
raster scenarios are labeled in -- so it can be used to pick which
raster/vector file to request.

Does NOT download or clip the actual NOAA SLR data (gitignored, manual
download per the project doc). This only computes which scenario label
(e.g. "2.5 ft") to go get.

Usage:
    source .venv/bin/activate
    python scripts/calc_scenario_water_level.py
"""

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_PATH = REPO_ROOT / "data" / "processed" / "tide_predictions_2026_27_navd88.csv"

REFERENCE_STATION = "san_francisco"  # matches the doc's own example CO-OPS query
EL_NINO_BUMP_FT = 1.0

# NOAA SLR scenarios available per the planning doc: whole feet, plus
# half-foot increments if the scenario lands near one.
AVAILABLE_RASTER_SCENARIOS_FT = [1, 1.5, 2, 2.5, 3]


def main():
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Expected {PREDICTIONS_PATH} -- run scripts/fetch_2026_27_predictions.py first."
        )

    rows = list(csv.DictReader(open(PREDICTIONS_PATH)))

    print("Highest predicted King Tide this winter, by station (ft above that station's own MHHW):")
    station_peaks = {}
    for station in sorted(set(r["station_name"] for r in rows)):
        highs = [r for r in rows if r["station_name"] == station and r["hilo_type"].startswith("H")]
        peak = max(highs, key=lambda r: float(r["prediction_ft_mhhw"]))
        station_peaks[station] = (float(peak["prediction_ft_mhhw"]), peak["datetime_gmt"])
        print(f"  {station:<15} {float(peak['prediction_ft_mhhw']):.3f} ft  ({peak['datetime_gmt']})")

    king_tide_ft, king_tide_dt = station_peaks[REFERENCE_STATION]
    scenario_ft = king_tide_ft + EL_NINO_BUMP_FT

    print(f"\nReference station: {REFERENCE_STATION}")
    print(f"Highest predicted King Tide: {king_tide_ft:.3f} ft above MHHW ({king_tide_dt})")
    print(f"+ El Nino bump: {EL_NINO_BUMP_FT:.1f} ft")
    print(f"= Scenario water level: {scenario_ft:.3f} ft above MHHW")

    nearest = min(AVAILABLE_RASTER_SCENARIOS_FT, key=lambda x: abs(x - scenario_ft))
    print(f"\nNearest available NOAA SLR raster scenario: {nearest} ft")
    print("(This picks which file to request -- the file itself still needs to be "
          "downloaded manually; see the project planning doc / README.)")


if __name__ == "__main__":
    main()
