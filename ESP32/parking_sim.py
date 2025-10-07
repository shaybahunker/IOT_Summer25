#!/usr/bin/env python3

import sys, time, json, random, threading
try:
    import serial  # pip install pyserial
except ImportError:
    print("Please install pyserial:  pip install pyserial")
    sys.exit(1)

USAGE = """
Parking Lot Simulator
---------------------
Usage:
  python parking_sim.py [PORT] [BAUD]

Defaults: PORT=COM5 (Windows) or /dev/ttyUSB0 (Linux/Mac), BAUD=115200

Interactive commands (type then press Enter):
  enter <plate>          -> simulate a car entering with that license plate
  free <spot_index>      -> free a specific spot (1..49), sets its distance "far"
  take <spot_index>      -> occupy a specific spot (1..49), sets its distance "near"
  problem <spot_index>   -> mark a spot as problem (orange)
  ok <spot_index>        -> clear problem flag
  quit                   -> exit the simulator
"""

NEAR_CM = 10     # occupied
FAR_CM  = 200    # free

def input_thread(ser, state):
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower() == "quit":
            os._exit(0)
        parts = line.split()
        if parts[0].lower() == "enter" and len(parts) >= 2:
            plate = " ".join(parts[1:])
            msg = {"type":"car_enter","plate":plate}
            ser.write((json.dumps(msg)+"\n").encode("utf-8"))
            print("->", msg)
        elif parts[0].lower() in ("free","take","problem","ok") and len(parts)==2:
            try:
                idx = int(parts[1])
                if not 1 <= idx <= 49:
                    print("Index must be 1..49")
                    continue
            except ValueError:
                print("Index must be an integer 1..49")
                continue
            if parts[0].lower() == "free":
                state["distances"][idx] = FAR_CM
            elif parts[0].lower() == "take":
                state["distances"][idx] = NEAR_CM
            elif parts[0].lower() == "problem":
                state["problems"].add(idx)
            elif parts[0].lower() == "ok":
                state["problems"].discard(idx)
            # push immediate update
            send_update(ser, state)
        else:
            print(USAGE)

def send_update(ser, state):
    # Build compact payload matching the ESP32 firmware
    payload = {
        "type":"sensor_update",
        # index 0 is None because spot 0 is the *real* ultrasonic sensor on the ESP32
        "distances":[None] + [state["distances"][i] for i in range(1,50)],
        "problems": sorted(list(state["problems"])),
    }
    ser.write((json.dumps(payload)+"\n").encode("utf-8"))
    print("->", payload)

def main():
    port = "COM5" if sys.platform.startswith("win") else "/dev/ttyUSB0"
    baud = 115200
    if len(sys.argv) >= 2:
        port = sys.argv[1]
    if len(sys.argv) >= 3:
        baud = int(sys.argv[2])

    try:
        ser = serial.Serial(port, baud, timeout=0.1)
    except Exception as e:
        print(f"Failed to open serial {port}: {e}")
        print(USAGE)
        sys.exit(1)

    # initial state: half free, half occupied randomly
    distances = [None] + [random.choice([NEAR_CM, FAR_CM]) for _ in range(49)]
    state = {"distances": {i: distances[i] for i in range(50)}, "problems": set()}

    # start interactive thread
    thr = threading.Thread(target=input_thread, args=(ser, state), daemon=True)
    thr.start()

    print(USAGE)
    print(f"Connected to {port} @ {baud}. Sending updates every 2 seconds...")

    # periodic updates
    t0 = time.time()
    while True:
        # small random drift to mimic cars moving
        for i in range(1,50):
            if state["distances"][i] == NEAR_CM and random.random() < 0.05:
                state["distances"][i] = FAR_CM
            elif state["distances"][i] == FAR_CM and random.random() < 0.05:
                state["distances"][i] = NEAR_CM
        send_update(ser, state)
        time.sleep(2.0)

if __name__ == "__main__":
    main()
