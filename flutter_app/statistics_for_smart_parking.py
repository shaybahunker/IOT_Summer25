import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from pathlib import Path

# Configuration
XLSX = "smart_parking_sim.xlsx"
SHEET = "window_5min_85-90%_comparisons"  # Need to edit when changing the excel sheet
OUTDIR = Path(".")
ROLL_WINDOW = 10
CARS_PER_DAY = 600
FUEL_L_PER_KM = 0.08
CO2_KG_PER_KM = 0.184

# Styling
plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 300,
    "font.size": 12,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.linewidth": 1.0,
    "lines.linewidth": 2.2,
})

def save_fig(fig, name):
    fig.tight_layout()
    fig.savefig(OUTDIR / f"{name}.png", bbox_inches="tight")
    plt.close(fig)

thousands = FuncFormatter(lambda x, _: f"{x:,.0f}")
one_decimal = FuncFormatter(lambda x, _: f"{x:,.1f}")
percent_fmt = FuncFormatter(lambda x, _: f"{x:.0f}%")

# Loading
wb = pd.ExcelFile(XLSX)
df = pd.read_excel(wb, sheet_name=SHEET)

# Preperation
df = df.dropna(subset=[
    "algo_drive_time_s","worst_drive_time_s",
    "algo_drive_distance_m","worst_drive_distance_m"
]).sort_values("arrival_id").reset_index(drop=True)

df["car_num"] = range(1, len(df)+1)

# Deltas
df["delta_time_s"] = df["worst_drive_time_s"] - df["algo_drive_time_s"]
df["delta_distance_m"] = df["worst_drive_distance_m"] - df["algo_drive_distance_m"]
df["percent_faster"] = 100 * (1 - df["algo_drive_time_s"] / df["worst_drive_time_s"]).clip(-500, 500)

# Fuel and CO₂
df["fuel_algo_L"]  = (df["algo_drive_distance_m"]  / 1000) * FUEL_L_PER_KM
df["fuel_worst_L"] = (df["worst_drive_distance_m"] / 1000) * FUEL_L_PER_KM
df["fuel_saved_L"] = df["fuel_worst_L"] - df["fuel_algo_L"]
df["cum_fuel_algo_L"]  = df["fuel_algo_L"].cumsum()
df["cum_fuel_worst_L"] = df["fuel_worst_L"].cumsum()
df["cum_fuel_saved_L"] = df["fuel_saved_L"].cumsum()
df["co2_saved_kg"] = (df["delta_distance_m"] / 1000) * CO2_KG_PER_KM

# Summary
avg_time_s = df["delta_time_s"].mean()
total_time_min = df["delta_time_s"].sum() / 60
avg_dist_m = df["delta_distance_m"].mean()
total_dist_km = df["delta_distance_m"].sum() / 1000

# Savings per car
fig, ax = plt.subplots(figsize=(6.2, 4.2))
ax.bar(["Avg Time Saved (s)", "Avg Distance Saved (m)"], [avg_time_s, avg_dist_m])
ax.set_title("Average Savings per Car (Algorithm vs Worst Case)")
ax.set_ylim(bottom=0)
for i, v in enumerate([avg_time_s, avg_dist_m]):
    ax.text(i, v, f"{v:,.1f}", ha="center", va="bottom")
save_fig(fig, "average_savings_per_car")

# Total savings
fig, ax = plt.subplots(figsize=(6.2, 4.2))
vals = [total_time_min, total_dist_km]
labels = ["Total Time Saved (min)", "Total Distance Saved (km)"]
ax.bar(labels, vals)
ax.set_title("Total Savings in Simulation")
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(thousands)
for i, v in enumerate(vals):
    ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom")
save_fig(fig, "total_savings")

# Time effeciency
df["roll_pct_fast"] = df["percent_faster"].rolling(ROLL_WINDOW, min_periods=ROLL_WINDOW).mean()
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(df["car_num"], df["roll_pct_fast"])
ax.set_title(f"Rolling Average Percent Faster")
ax.set_xlabel("Car Number")
ax.set_ylabel("Percent Faster than Worst Case")
ax.grid(True, alpha=0.3)
ax.set_ylim(bottom=min(0, df["roll_pct_fast"].min(skipna=True) or 0))
ax.yaxis.set_major_formatter(percent_fmt)
save_fig(fig, "rolling_percent_faster")


df["cum_time_min"] = df["delta_time_s"].cumsum() / 60
df["cum_dist_km"] = df["delta_distance_m"].cumsum() / 1000
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(df["car_num"], df["cum_time_min"], label="Time Saved (min)")
ax.plot(df["car_num"], df["cum_dist_km"], label="Distance Saved (km)")
ax.set_title("Cumulative Savings Over Simulation")
ax.set_xlabel("Car Number")
ax.set_ylabel("Cumulative Value")
ax.grid(True, alpha=0.3)
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(thousands)
ax.legend(frameon=False)
save_fig(fig, "cumulative_savings")

# Daily estimations
daily_time_hr = (avg_time_s * CARS_PER_DAY) / 3600
daily_dist_km = (avg_dist_m * CARS_PER_DAY) / 1000
daily_fuel_l = daily_dist_km * FUEL_L_PER_KM
daily_co2_kg = daily_dist_km * CO2_KG_PER_KM

fig, ax = plt.subplots(figsize=(6.2, 4.2))
labels = ["Time Saved (h)", "Distance Saved (km)", "Fuel Saved (L)", "CO2 Reduced (kg)"]
vals = [daily_time_hr, daily_dist_km, daily_fuel_l, daily_co2_kg]
ax.bar(labels, vals)
ax.set_title(f"Projected Daily Impact ({CARS_PER_DAY:,} Cars per Day)")
ax.set_ylim(bottom=0)
for i, v in enumerate(vals):
    ax.text(i, v, f"{v:,.1f}", ha="center", va="bottom")
plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
save_fig(fig, "daily_projection")

# Fuel usage comparison
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(df["car_num"], df["cum_fuel_worst_L"], label="Worst Case Cumulative Fuel (L)")
ax.plot(df["car_num"], df["cum_fuel_algo_L"],  label="Algorithm Cumulative Fuel (L)")
ax.fill_between(df["car_num"], df["cum_fuel_algo_L"], df["cum_fuel_worst_L"],
                color="lightgreen", alpha=0.3, label="Fuel Saved")
ax.set_title("Cumulative Fuel Usage Comparison")
ax.set_xlabel("Car Number")
ax.set_ylabel("Cumulative Fuel (L)")
ax.grid(True, alpha=0.3)
ax.set_ylim(bottom=0)
ax.yaxis.set_major_formatter(one_decimal)
ax.legend(frameon=False)
save_fig(fig, "fuel_usage_comparison")

print("Saved graphs:",
      "average_savings_per_car.png, total_savings.png, rolling_percent_faster.png,",
      "cumulative_savings.png, daily_projection.png, fuel_usage_comparison.png")
