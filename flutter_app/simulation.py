# smart_parking_sim.py
# Phases:
# 1) Fill to 50% using closest-by-Manhattan.
# 2) One more arrival: compare best vs worst (farthest).
# 3) Greedy-fill to >=85% occupancy (arrivals only; no departures processed).
# 4) Run a window (5 min * WINDOW_MULTIPLIER) with Poisson arrivals + exponential stays.
#    For every arrival in that window, log best vs worst into a NEW Excel sheet.
# Outputs: ./smart_parking_sim.xlsx

import math
import heapq
import random
from typing import List, Tuple, Dict
import pandas as pd

# Consts
SEED = 42
# Arrivals (Poisson)
LAMBDA_PER_MIN = 6.0              # arrivals per minute
# Stay times
STAY_MEAN_SEC = 150.0
STAY_MIN_SEC  = 60.0
# Driving realism:
DRIVE_SPEED_KMH = 7.0             # ~1.94 m/s inside lot
CELL_CM = 300.0                   # 3 m per grid cell
FLOOR_PENALTY_CM = 15000.0        # +150 m to reach floor 2
PATH_MULTIPLIER = 3.0             # snaking aisles/turns factor
FIXED_OVERHEAD_SEC = 120.0        # gate, slow, park maneuver
# Targets and window:
TARGET_OCCUPIED_50 = 0.50         # phase-1 stop threshold
TARGET_OCCUPIED_LO = 0.85         # reach at least 85% before window
WINDOW_SECONDS = 300.0            # 5 minutes base
WINDOW_MULTIPLIER = 10            # 10× more data → 50 minutes total simulated
# Output:
OUT_XLSX = "smart_parking_sim.xlsx"

random.seed(SEED)
DRIVE_SPEED_MPS = DRIVE_SPEED_KMH * 1000 / 3600.0
LAMBDA_PER_SEC  = LAMBDA_PER_MIN / 60.0

# Parking lots coordinates
spotXY: List[Tuple[int, int, int]] = [
    (0,1,1),
    (1,1,1),(2,1,1),(3,1,1),(4,1,1),(5,1,1),
    (1,2,1),(2,2,1),(3,2,1),(4,2,1),(5,2,1),
    (1,3,1),(2,3,1),(3,3,1),(4,3,1),(5,3,1),
    (1,4,1),(2,4,1),(3,4,1),(4,4,1),(5,4,1),
    (1,5,1),(2,5,1),(3,5,1),(4,5,1),(5,5,1),
    (1,1,2),(2,1,2),(3,1,2),(4,1,2),(5,1,2),
    (1,2,2),(2,2,2),(3,2,2),(4,2,2),(5,2,2),
    (1,3,2),(2,3,2),(3,3,2),(4,3,2),(5,3,2),
    (1,4,2),(2,4,2),(3,4,2),(4,4,2),(5,4,2),
    (1,5,2),(2,5,2),(3,5,2),(4,5,2)
]
TOTAL_SPOTS = len(spotXY)
TARGET_COUNT_50 = int(TOTAL_SPOTS * TARGET_OCCUPIED_50)           # 25
TARGET_COUNT_LO = int(math.ceil(TOTAL_SPOTS * TARGET_OCCUPIED_LO)) # 43

# Helpers
def manhattan_distance_m(spot_id: int) -> float:
    x, y, floor = spotXY[spot_id]
    base_cm = (x + y) * CELL_CM
    if floor == 2:
        base_cm += FLOOR_PENALTY_CM
    return base_cm / 100.0

def effective_drive_distance_m(spot_id: int) -> float:
    return manhattan_distance_m(spot_id) * PATH_MULTIPLIER

def drive_time_seconds(spot_id: int) -> float:
    dist_m = effective_drive_distance_m(spot_id)
    return FIXED_OVERHEAD_SEC + (dist_m / DRIVE_SPEED_MPS)

def choose_best(free_set: set) -> int:
    #Using manhattan distance
    return min(free_set, key=lambda s: (manhattan_distance_m(s), s))

def choose_worst(free_set: set) -> int:
    return max(free_set, key=lambda s: (manhattan_distance_m(s), s))

def exp_interarrival_seconds(rate_per_sec: float) -> float:
    u = random.random()
    return -math.log(1.0 - u) / rate_per_sec

def sample_stay_seconds() -> float:
    u = random.random()
    stay = -math.log(1.0 - u) * STAY_MEAN_SEC
    return max(stay, STAY_MIN_SEC)

# Simulation
def main():
    # State
    sim_time_s = 0.0
    arrival_id = 0

    free_spots = set(range(TOTAL_SPOTS))
    occupied_spots = set()
    dep_heap: List[Tuple[float, int]] = [] # min-heap of (leave_time, spot_id)

    # First step - fill till 50% occupied
    rows_first_phase: List[Dict] = []

    while len(occupied_spots) < TARGET_COUNT_50 and free_spots:
        sim_time_s += exp_interarrival_seconds(LAMBDA_PER_SEC)
        arrival_id += 1

        best = choose_best(free_spots)
        dist_m = effective_drive_distance_m(best)
        time_s = drive_time_seconds(best)

        x, y, fl = spotXY[best]
        rows_first_phase.append({
            "arrival_id": arrival_id,
            "chosen_spot": best,
            "x": x, "y": y, "floor": fl,
            "drive_distance_m": round(dist_m, 1),
            "drive_time_s": round(time_s, 1),
            "occupancy_after": len(occupied_spots) + 1
        })

        free_spots.remove(best)
        occupied_spots.add(best)
        heapq.heappush(dep_heap, (sim_time_s + sample_stay_seconds(), best))

    # Step 2: 1 more arrival above the 50%
    comparison_row = {}
    if free_spots:
        sim_time_s += exp_interarrival_seconds(LAMBDA_PER_SEC)
        arrival_id += 1

        best = choose_best(free_spots)
        worst = choose_worst(free_spots)

        best_dist = effective_drive_distance_m(best)
        worst_dist = effective_drive_distance_m(worst)
        best_time = drive_time_seconds(best)
        worst_time = drive_time_seconds(worst)

        comparison_row = {
            "arrival_id": arrival_id,
            "algo_spot": best,
            "algo_drive_distance_m": round(best_dist, 1),
            "algo_drive_time_s": round(best_time, 1),
            "worst_spot": worst,
            "worst_drive_distance_m": round(worst_dist, 1),
            "worst_drive_time_s": round(worst_time, 1),
            "delta_distance_m": round(worst_dist - best_dist, 1),
            "delta_time_s": round(worst_time - best_time, 1),
        }

        free_spots.remove(best)
        occupied_spots.add(best)
        heapq.heappush(dep_heap, (sim_time_s + sample_stay_seconds(), best))

    # Step 3: fill til 85% occupied
    while len(occupied_spots) < TARGET_COUNT_LO and free_spots:
        sim_time_s += exp_interarrival_seconds(LAMBDA_PER_SEC)
        arrival_id += 1
        best = choose_best(free_spots)
        free_spots.remove(best)
        occupied_spots.add(best)
        heapq.heappush(dep_heap, (sim_time_s + sample_stay_seconds(), best))

    # Step 3b: long churn window
    window_start = sim_time_s
    window_end   = window_start + WINDOW_SECONDS * WINDOW_MULTIPLIER
    rows_window: List[Dict] = []

    # Next arrival after window start
    next_arrival_t = sim_time_s + exp_interarrival_seconds(LAMBDA_PER_SEC)

    while True:
        next_depart_t = dep_heap[0][0] if dep_heap else float("inf")
        next_event_t = min(next_arrival_t, next_depart_t)

        if next_event_t > window_end:
            break  # window done

        sim_time_s = next_event_t

        if next_depart_t <= next_arrival_t:
            # Process a departure
            _, spot = heapq.heappop(dep_heap)
            if spot in occupied_spots:
                occupied_spots.remove(spot)
                free_spots.add(spot)
        else:
            # Process an arrival inside window
            arrival_id += 1
            if free_spots:
                best = choose_best(free_spots)
                worst = choose_worst(free_spots) if len(free_spots) > 1 else best

                best_dist = effective_drive_distance_m(best)
                worst_dist = effective_drive_distance_m(worst)
                best_time = drive_time_seconds(best)
                worst_time = drive_time_seconds(worst)

                rows_window.append({
                    "arrival_id": arrival_id,
                    "sim_time_s": round(sim_time_s - window_start, 1),
                    "occupancy_before": len(occupied_spots),
                    "algo_spot": best,
                    "algo_drive_distance_m": round(best_dist, 1),
                    "algo_drive_time_s": round(best_time, 1),
                    "worst_spot": worst,
                    "worst_drive_distance_m": round(worst_dist, 1),
                    "worst_drive_time_s": round(worst_time, 1),
                    "delta_distance_m": round(worst_dist - best_dist, 1),
                    "delta_time_s": round(worst_time - best_time, 1),
                })

                free_spots.remove(best)
                occupied_spots.add(best)
                heapq.heappush(dep_heap, (sim_time_s + sample_stay_seconds(), best))

            # schedule next arrival
            next_arrival_t = sim_time_s + exp_interarrival_seconds(LAMBDA_PER_SEC)

    # Write to excel sheet
    df_first = pd.DataFrame(rows_first_phase)
    df_comp  = pd.DataFrame([comparison_row]) if comparison_row else pd.DataFrame()
    df_window = pd.DataFrame(rows_window)
    df_params = pd.DataFrame({
        "SEED": [SEED],
        "LAMBDA_PER_MIN": [LAMBDA_PER_MIN],
        "DRIVE_SPEED_KMH": [DRIVE_SPEED_KMH],
        "CELL_CM": [CELL_CM],
        "FLOOR_PENALTY_CM": [FLOOR_PENALTY_CM],
        "PATH_MULTIPLIER": [PATH_MULTIPLIER],
        "FIXED_OVERHEAD_SEC": [FIXED_OVERHEAD_SEC],
        "STAY_MEAN_SEC": [STAY_MEAN_SEC],
        "STAY_MIN_SEC": [STAY_MIN_SEC],
        "TARGET_50_count": [TARGET_COUNT_50],
        "TARGET_85_count": [TARGET_COUNT_LO],
        "WINDOW_SECONDS": [WINDOW_SECONDS],
        "WINDOW_MULTIPLIER": [WINDOW_MULTIPLIER],
        "TOTAL_SPOTS": [TOTAL_SPOTS],
    })

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        df_first.to_excel(writer, index=False, sheet_name="arrivals_up_to_50%")
        df_comp.to_excel(writer, index=False, sheet_name="comparison_after_50%")
        df_window.to_excel(writer, index=False, sheet_name="window_5min_85-90%_comparisons")
        df_params.to_excel(writer, index=False, sheet_name="params")

if __name__ == "__main__":
    main()
