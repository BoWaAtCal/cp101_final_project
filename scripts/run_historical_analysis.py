"""
El Nino historical comparison + inputs for scripts/visualize_historical_analysis.py.

For each historical El Nino winter in data/processed/tide_levels_navd88.csv
(1982-83, 1997-98, 2015-16), compares each station's high water against the
nearest PRECEDING ENSO-neutral winter at the same station. "Neutral" means
all three winter RONI seasons (NDJ, DJF, JFM) are within +/-0.5. 2023-24 is
left out: its nearest preceding neutral winter (2019-20) is four years back.

Anomaly = El Nino winter statistic - neutral winter statistic, in ft (MHHW,
so each station is compared against its own datum). Station anomalies are
then averaged into one value per event. Stations with no data for either
winter are skipped (see docs/datum_handling.md for the known gaps).

Neutral-winter hourly water levels are downloaded from CO-OPS on the first
run and cached in data/raw/tide_levels/, so later runs work offline.

Usage:
    python scripts/run_historical_analysis.py

Outputs (outputs/historical_analysis/):
    historical_event_summary.csv  one row per El Nino winter
    station_anomalies.csv         one row per El Nino winter x station
    predicted_monthly_peaks.csv   2026-27 monthly max predicted high tide,
                                  ft above MHHW, one column per station
    top_olu_people.csv            OLUs ranked by people exposed (2.5 ft)
"""

import io
import time
import urllib.request
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "tide_levels"
PROCESSED = REPO_ROOT / "data" / "processed"
RONI_PATH = REPO_ROOT / "data" / "raw" / "RONI.ascii.txt"
EXPOSURE_CSV = REPO_ROOT / "outputs" / "exposure_by_olu_2_5ft.csv"
OUT_DIR = REPO_ROOT / "outputs" / "historical_analysis"

STATIONS = {
    "9414290": "san_francisco",
    "9414750": "alameda",
    "9414863": "richmond",
    "9414523": "redwood_city",
}
STATION_LABELS = {
    "alameda": "Alameda",
    "redwood_city": "Redwood City",
    "richmond": "Richmond",
    "san_francisco": "San Francisco",
}
EL_NINO_WINTERS = ["1982-83", "1997-98", "2015-16"]
NEUTRAL_THRESHOLD = 0.5

DATAGETTER_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    "?product=hourly_height&station={station}&begin_date={begin}&end_date={end}"
    "&datum=MHHW&units=english&time_zone=gmt&format=csv&application=bay_flood_hotspots"
)


def winter_start(winter):
    """'1997-98' -> 1997 (the year the Nov-Mar winter starts)."""
    return int(winter[:4])


def winter_label(start_year):
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def load_winter_roni():
    """Mean and max |anomaly| of NDJ, DJF, JFM for each winter, keyed by start year."""
    roni = pd.read_csv(RONI_PATH, sep=r"\s+")
    roni = roni.set_index(["SEAS", "YR"])["ANOM"]
    out = {}
    for year in range(roni.index.get_level_values("YR").min(), roni.index.get_level_values("YR").max()):
        try:
            vals = [roni[("NDJ", year)], roni[("DJF", year + 1)], roni[("JFM", year + 1)]]
        except KeyError:
            continue
        out[year] = {"mean": sum(vals) / 3, "max_abs": max(abs(v) for v in vals)}
    return out


def nearest_preceding_neutral(start_year, roni):
    year = start_year - 1
    while year in roni:
        if roni[year]["max_abs"] < NEUTRAL_THRESHOLD:
            return year
        year -= 1
    raise ValueError(f"No neutral winter found before {start_year}")


def load_hourly_mhhw(station, name, winter):
    """Hourly water level (ft above MHHW) for one station/winter, cached in data/raw/."""
    path = RAW_DIR / f"{name}_{winter}_mhhw.csv"
    if not path.exists():
        start = winter_start(winter)
        url = DATAGETTER_URL.format(station=station, begin=f"{start}1101", end=f"{start + 1}0331")
        with urllib.request.urlopen(url, timeout=30) as r:
            path.write_text(r.read().decode("utf-8"))
        time.sleep(0.3)
    text = path.read_text()
    if "Error" in text[:200]:
        return None
    levels = pd.read_csv(io.StringIO(text), skipinitialspace=True)["Water Level"].dropna()
    return levels if len(levels) else None


def station_anomalies(roni):
    rows = []
    for event in EL_NINO_WINTERS:
        neutral = winter_label(nearest_preceding_neutral(winter_start(event), roni))
        for station, name in STATIONS.items():
            ev = load_hourly_mhhw(station, name, event)
            ne = load_hourly_mhhw(station, name, neutral)
            if ev is None or ne is None:
                print(f"  {event} {name:<15} skipped (no data for {'event' if ev is None else 'neutral'} winter)")
                continue
            rows.append({
                "event_winter": event,
                "neutral_winter": neutral,
                "station": name,
                "p95_anomaly_ft": ev.quantile(0.95) - ne.quantile(0.95),
                "max_anomaly_ft": ev.max() - ne.max(),
            })
    return pd.DataFrame(rows)


def event_summary(stations, roni):
    summary = stations.groupby(["event_winter", "neutral_winter"], as_index=False).agg(
        p95_anomaly_ft=("p95_anomaly_ft", "mean"),
        max_anomaly_ft=("max_anomaly_ft", "mean"),
        n_stations=("station", "count"),
    )
    summary["winter_roni"] = summary["event_winter"].map(lambda w: roni[winter_start(w)]["mean"])
    return summary


def monthly_predicted_peaks():
    pred = pd.read_csv(PROCESSED / "tide_predictions_2026_27_navd88.csv")
    pred = pred[pred["hilo_type"].isin(["H", "HH"])]
    pred["Month"] = pd.to_datetime(pred["datetime_gmt"]).dt.strftime("%Y-%m")
    peaks = pred.pivot_table(index="Month", columns="station_name",
                             values="prediction_ft_mhhw", aggfunc="max")
    return peaks.rename(columns=STATION_LABELS).reset_index()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    roni = load_winter_roni()

    print("Comparing El Nino winters against the nearest preceding neutral winter")
    stations = station_anomalies(roni)
    summary = event_summary(stations, roni)
    stations.to_csv(OUT_DIR / "station_anomalies.csv", index=False)
    summary.to_csv(OUT_DIR / "historical_event_summary.csv", index=False)
    print(summary.round(3).to_string(index=False))

    monthly_predicted_peaks().to_csv(OUT_DIR / "predicted_monthly_peaks.csv", index=False)

    exposure = pd.read_csv(EXPOSURE_CSV).sort_values("people", ascending=False)
    exposure[["olu_id", "olu_name", "people", "vuln_people", "road_mi", "trail_mi"]].to_csv(
        OUT_DIR / "top_olu_people.csv", index=False)

    print(f"\nWrote inputs for visualize_historical_analysis.py to {OUT_DIR}")


if __name__ == "__main__":
    main()
