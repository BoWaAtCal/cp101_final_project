"""
Step 1: CO-OPS water levels, converted to a common vertical datum (NAVD88).

Pulls hourly water levels for the 4 Bay Area stations x 4 winters listed in
the project planning doc, in MHHW (as the doc's example query specifies),
then converts each series to NAVD88 using that STATION's own official
MHHW<->NAVD88 offset (from the CO-OPS Datums API) -- these offsets are NOT
the same Bay-wide; they range ~5.9-7.0 ft across these 4 stations because
tidal range amplifies moving south/inland in the Bay. See
docs/datum_handling.md for why this matters and isn't a single number.

Usage:
    source .venv/bin/activate
    python scripts/fetch_tide_levels.py

Outputs:
    data/raw/tide_levels/<station>_<winter>_mhhw.csv      (as downloaded)
    data/processed/tide_levels_navd88.csv                  (all stations/
        winters combined, water level converted to NAVD88, plus the MHHW
        original and the offset used, for traceability)
    data/raw/RONI.ascii.txt                                 (ENSO index)
"""

import csv
import io
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "tide_levels"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RONI_PATH = REPO_ROOT / "data" / "raw" / "RONI.ascii.txt"

STATIONS = {
    "9414290": "san_francisco",
    "9414750": "alameda",
    "9414863": "richmond",
    "9414523": "redwood_city",
}

# Nov 1 - Mar 31. Per the doc: 1997-98 and 2015-16 are strong El Nino
# winters; 1982-83 and 2023-24 need confirming against RONI (both are
# historically strong/moderate El Nino winters too -- this script does not
# itself classify them, it just pulls the data; see RONI.ascii.txt).
WINTERS = {
    "1982-83": ("19821101", "19830331"),
    "1997-98": ("19971101", "19980331"),
    "2015-16": ("20151101", "20160331"),
    "2023-24": ("20231101", "20240331"),
}

DATUMS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station}/datums.json?units=english"
DATAGETTER_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    "?product=hourly_height&station={station}&begin_date={begin}&end_date={end}"
    "&datum=MHHW&units=english&time_zone=gmt&format=csv&application=bay_flood_hotspots"
)
RONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"


def fetch(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8")


def get_mhhw_navd88_offset(station: str) -> float:
    """MHHW minus NAVD88, in feet, at this station's own datum. Positive
    means MHHW sits above NAVD88 (true for all 4 of these stations)."""
    import json

    data = json.loads(fetch(DATUMS_URL.format(station=station)))
    vals = {d["name"]: d["value"] for d in data["datums"]}
    return vals["MHHW"] - vals["NAVD88"]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RONI_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching RONI (ENSO index)...")
    RONI_PATH.write_text(fetch(RONI_URL))
    print(f"  wrote {RONI_PATH}")

    print("\nFetching station MHHW<->NAVD88 offsets...")
    offsets = {}
    for station, name in STATIONS.items():
        offsets[station] = get_mhhw_navd88_offset(station)
        print(f"  {name:<15} {station}  MHHW - NAVD88 = {offsets[station]:+.2f} ft")
        time.sleep(0.3)

    combined_rows = []
    print("\nFetching hourly water levels (MHHW) and converting to NAVD88...")
    for station, name in STATIONS.items():
        for winter, (begin, end) in WINTERS.items():
            url = DATAGETTER_URL.format(station=station, begin=begin, end=end)
            raw_csv = fetch(url)
            raw_path = RAW_DIR / f"{name}_{winter}_mhhw.csv"
            raw_path.write_text(raw_csv)

            if "Error" in raw_csv[:200]:
                print(f"  {name:<15} {winter}  ERROR: {raw_csv.strip()[:150]}")
                continue

            reader = csv.DictReader(io.StringIO(raw_csv))
            n = 0
            for row in reader:
                # CO-OPS hourly_height CSV columns: "Date Time", " Water Level", ...
                ts_key = "Date Time" if "Date Time" in row else list(row.keys())[0]
                wl_key = next((k for k in row if "Water Level" in k), None)
                if wl_key is None or not row[wl_key].strip():
                    continue
                mhhw_val = float(row[wl_key])
                combined_rows.append(
                    {
                        "station_id": station,
                        "station_name": name,
                        "winter": winter,
                        "datetime_gmt": row[ts_key],
                        "water_level_ft_mhhw": mhhw_val,
                        "mhhw_minus_navd88_ft": offsets[station],
                        "water_level_ft_navd88": mhhw_val + offsets[station],
                    }
                )
                n += 1
            print(f"  {name:<15} {winter}  {n} hourly obs")
            time.sleep(0.3)

    out_path = PROCESSED_DIR / "tide_levels_navd88.csv"
    if combined_rows:
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=combined_rows[0].keys())
            writer.writeheader()
            writer.writerows(combined_rows)
        print(f"\nWrote {out_path} ({len(combined_rows)} rows)")
    else:
        print("\nNo rows fetched -- nothing written.")


if __name__ == "__main__":
    main()
