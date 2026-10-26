"""Visualize the CP101 El Nino historical and flood-exposure analysis.

Run from the repository root:
    python scripts/visualize_historical_analysis.py

The script reads the compact CSV outputs produced by
``run_historical_analysis.py`` and writes a single PNG dashboard.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "outputs" / "historical_analysis"
OUTPUT_PATH = DATA_DIR / "el_nino_historical_visualizations.png"

NAVY = "#16324F"
BLUE = "#2F6690"
TEAL = "#3A7D78"
ORANGE = "#D97706"
PURPLE = "#7C3AED"
GRAY = "#5B6573"
GRID = "#D9DEE5"


def label_bars(axis, decimals=2):
    """Add compact value labels to every bar container on an axis."""
    for container in axis.containers:
        axis.bar_label(
            container,
            fmt=f"%.{decimals}f",
            padding=3,
            fontsize=8,
            color=NAVY,
        )


def main():
    events = pd.read_csv(DATA_DIR / "historical_event_summary.csv")
    monthly = pd.read_csv(DATA_DIR / "predicted_monthly_peaks.csv")
    top_olu = pd.read_csv(DATA_DIR / "top_olu_people.csv").head(10)

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "axes.titleweight": "bold",
        "axes.edgecolor": GRID,
        "axes.labelcolor": NAVY,
        "xtick.color": GRAY,
        "ytick.color": GRAY,
    })

    figure, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    figure.patch.set_facecolor("white")
    figure.suptitle(
        "Bay Area El Niño water levels and 2.5-ft flood exposure",
        fontsize=19,
        fontweight="bold",
        color=NAVY,
    )

    # Panel A: event-level high-water anomalies.
    axis = axes[0, 0]
    x = np.arange(len(events))
    width = 0.34
    axis.bar(
        x - width / 2,
        events["p95_anomaly_ft"],
        width,
        color=TEAL,
        label="95th-percentile anomaly",
    )
    axis.bar(
        x + width / 2,
        events["max_anomaly_ft"],
        width,
        color=ORANGE,
        label="Maximum anomaly",
    )
    axis.axhline(1.0, color=NAVY, linewidth=1.4, linestyle="--", label="+1-ft assumption")
    axis.set_xticks(x, events["event_winter"])
    axis.set_ylabel("Anomaly versus matched neutral winter (ft)")
    axis.set_title("A. High-water anomalies by El Niño winter")
    axis.set_ylim(0, max(1.45, events["max_anomaly_ft"].max() + 0.2))
    axis.legend(frameon=False, loc="upper right", fontsize=8)
    axis.grid(axis="y", color=GRID, linewidth=0.7)
    axis.set_axisbelow(True)
    label_bars(axis)

    # Panel B: descriptive RONI relationship. Three events are labeled to
    # make the very small sample size explicit rather than imply a forecast.
    axis = axes[0, 1]
    axis.scatter(
        events["winter_roni"],
        events["p95_anomaly_ft"],
        s=95,
        color=BLUE,
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )
    slope, intercept = np.polyfit(events["winter_roni"], events["p95_anomaly_ft"], 1)
    line_x = np.linspace(events["winter_roni"].min() - 0.02, events["winter_roni"].max() + 0.02, 100)
    axis.plot(line_x, slope * line_x + intercept, color=BLUE, linestyle="--", linewidth=1.4)
    correlation = events["winter_roni"].corr(events["p95_anomaly_ft"])
    for _, row in events.iterrows():
        axis.annotate(
            row["event_winter"],
            (row["winter_roni"], row["p95_anomaly_ft"]),
            xytext=(6, 7),
            textcoords="offset points",
            fontsize=9,
            color=NAVY,
        )
    axis.set_xlabel("Winter RONI (mean of NDJ, DJF, JFM)")
    axis.set_ylabel("95th-percentile anomaly (ft)")
    axis.set_title(f"B. RONI and high-water anomaly (r={correlation:.2f}, n=3)")
    axis.text(
        0.02,
        0.03,
        "Descriptive only: three similarly strong events do not support a predictive slope.",
        transform=axis.transAxes,
        fontsize=8.5,
        color=GRAY,
    )
    axis.grid(color=GRID, linewidth=0.7)
    axis.set_axisbelow(True)

    # Panel C: monthly predicted astronomical tide peaks.
    axis = axes[1, 0]
    station_colors = {
        "Alameda": BLUE,
        "Redwood City": TEAL,
        "Richmond": ORANGE,
        "San Francisco": PURPLE,
    }
    for station, color in station_colors.items():
        axis.plot(
            monthly["Month"],
            monthly[station],
            marker="o",
            markersize=5,
            linewidth=2,
            color=color,
            label=station,
        )
    axis.set_ylabel("Monthly maximum (ft above MHHW)")
    axis.set_title("C. 2026–27 predicted astronomical tide peaks")
    axis.legend(frameon=False, ncol=2, fontsize=8)
    axis.grid(axis="y", color=GRID, linewidth=0.7)
    axis.set_axisbelow(True)
    axis.tick_params(axis="x", rotation=25)

    # Panel D: top OLUs by exposed population.
    axis = axes[1, 1]
    ranked = top_olu.sort_values("people", ascending=True)
    bars = axis.barh(ranked["olu_name"], ranked["people"], color=TEAL)
    axis.bar_label(bars, labels=[f"{value:,.0f}" for value in ranked["people"]], padding=4, fontsize=8)
    axis.set_xlabel("People exposed")
    axis.set_title("D. Top OLUs under the 2.5-ft scenario")
    axis.grid(axis="x", color=GRID, linewidth=0.7)
    axis.set_axisbelow(True)
    axis.set_xlim(0, ranked["people"].max() * 1.18)

    figure.text(
        0.01,
        0.005,
        "Historical baseline: nearest preceding neutral winter at the same station. "
        "Predictions are astronomical tides, not storm-surge forecasts. Population exposure is area-weighted by block group.",
        fontsize=8.5,
        color=GRAY,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
