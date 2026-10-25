"""
2026-27 high/low tide predictions (the forward-looking winter the planning
doc's WINTERS note mentions: "2026-27 high/low predictions"), converted to
NAVD88 the same way as scripts/fetch_tide_levels.py.

This is predicted (astronomical) tide data, not observed -- it's the
baseline tide curve to apply a King Tide + El Nino bump on top of for the
2026-27 forward scenario. Building that scenario itself is separate,
downstream work; this script only pulls and converts the predictions.

Usage:
    source .venv/bin/activate
    python scripts/fetch_2026_27_predictions.py

Outputs:
    data/raw/tide_levels/<station>_2026-27_predictions_mhhw.csv  (as downloaded)
    data/processed/tide_predictions_2026_27_navd88.csv            (all 4
        stations combined, high/low predictions converted to NAVD88)
"""

import csv
import io
import json
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "tide_levels"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

STATIONS = {
    "9414290": "san_francisco",
    "9414750": "alameda",
    "9414863": "richmond",
    "9414523": "redwood_city",
}

BEGIN_DATE, END_DATE = "20261101", "20270331"  # Nov 1, 2026 - Mar 31, 2027

DATUMS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station}/datums.json?units=english"
PREDICTIONS_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    "?product=predictions&station={station}&begin_date={begin}&end_date={end}"
    "&datum=MHHW&units=english&time_zone=gmt&interval=hilo&format=csv&application=bay_flood_hotspots"
)


def fetch(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8")


def get_mhhw_navd88_offset(station: str) -> float:
    data = json.loads(fetch(DATUMS_URL.format(station=station)))
    vals = {d["name"]: d["value"] for d in data["datums"]}
    return vals["MHHW"] - vals["NAVD88"]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching station MHHW<->NAVD88 offsets...")
    offsets = {}
    for station, name in STATIONS.items():
        offsets[station] = get_mhhw_navd88_offset(station)
        print(f"  {name:<15} {station}  MHHW - NAVD88 = {offsets[station]:+.2f} ft")
        time.sleep(0.3)

    combined_rows = []
    print(f"\nFetching {BEGIN_DATE}-{END_DATE} high/low predictions (MHHW) and converting to NAVD88...")
    for station, name in STATIONS.items():
        url = PREDICTIONS_URL.format(station=station, begin=BEGIN_DATE, end=END_DATE)
        raw_csv = fetch(url)
        raw_path = RAW_DIR / f"{name}_2026-27_predictions_mhhw.csv"
        raw_path.write_text(raw_csv)

        if "Error" in raw_csv[:200]:
            print(f"  {name:<15} ERROR: {raw_csv.strip()[:150]}")
            continue

        reader = csv.DictReader(io.StringIO(raw_csv))
        n = 0
        for row in reader:
            ts_key = "Date Time" if "Date Time" in row else list(row.keys())[0]
            pred_key = next((k for k in row if "Prediction" in k), None)
            type_key = next((k for k in row if "Type" in k), None)
            if pred_key is None or not row[pred_key].strip():
                continue
            mhhw_val = float(row[pred_key])
            combined_rows.append(
                {
                    "station_id": station,
                    "station_name": name,
                    "datetime_gmt": row[ts_key],
                    "hilo_type": row[type_key].strip() if type_key else "",
                    "prediction_ft_mhhw": mhhw_val,
                    "mhhw_minus_navd88_ft": offsets[station],
                    "prediction_ft_navd88": mhhw_val + offsets[station],
                }
            )
            n += 1
        print(f"  {name:<15} {n} high/low predictions")
        time.sleep(0.3)

    out_path = PROCESSED_DIR / "tide_predictions_2026_27_navd88.csv"
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
