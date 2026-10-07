"""
Load cell (Omega LC103B-3K) live force-vs-time recording on an NI-9205.

Tares at no load, then shows a live graph of force over time while you add
or remove weights. Saves a CSV of the data and a PNG of the final graph.

How to use:
  1. Close the NI MAX Test Panel (only one program can use the module at a time).
  2. Start with NO load on the load cell. It tares for a few seconds.
  3. When the graph window opens, add/remove weights whenever you like.
     Press "m" with the graph window selected to drop a marker line
     (e.g. each time you hang a weight).
  4. It stops after TOTAL_SECONDS, or earlier if you close the graph
     window or press Ctrl+C in the terminal.
"""

import csv
from datetime import datetime

import matplotlib.pyplot as plt
import nidaqmx
import numpy as np
from nidaqmx.constants import AcquisitionType, TerminalConfiguration, VoltageUnits

# ---------------- Settings ----------------
DEVICE_CHANNEL = "cDAQ1Mod4/ai1"    # NI-9205 is in slot 4
EXCITATION_V = 10.00                # measured Red-to-Black voltage
SENSITIVITY_MV_PER_V = 3.0          # LC103B datasheet
CAPACITY_LBF = 3000.0               # LC103B-3K
FLIP_SIGN = False                   # set True if hanging weight reads negative

SAMPLE_RATE = 1000                  # Hz, hardware sample rate
BLOCK_SIZE = 100                    # samples averaged per point -> 10 points/s
TARE_SECONDS = 3                    # no-load averaging at the start
TOTAL_SECONDS = 120                 # max recording time
# ------------------------------------------

FULL_SCALE_V = SENSITIVITY_MV_PER_V / 1000.0 * EXCITATION_V   # 0.030 V at 10 V
LBF_PER_VOLT = CAPACITY_LBF / FULL_SCALE_V                     # 100,000 lbf/V at 10 V
BLOCK_TIME = BLOCK_SIZE / SAMPLE_RATE
SIGN = -1.0 if FLIP_SIGN else 1.0

times, volts, forces, markers = [], [], [], []


def read_block(task):
    """Read one block and return its average voltage."""
    return float(np.mean(task.read(number_of_samples_per_channel=BLOCK_SIZE, timeout=5.0)))


with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan(
        DEVICE_CHANNEL,
        terminal_config=TerminalConfiguration.DIFF,
        min_val=-0.2,
        max_val=0.2,
        units=VoltageUnits.VOLTS,
    )
    task.timing.cfg_samp_clk_timing(
        rate=SAMPLE_RATE,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=SAMPLE_RATE * 10,  # 10 s buffer so plotting can't fall behind
    )
    task.start()

    # ---- Tare ----
    print(f"Taring for {TARE_SECONDS} s - keep the load cell unloaded...")
    n_tare = int(TARE_SECONDS / BLOCK_TIME)
    tare_v = float(np.mean([read_block(task) for _ in range(n_tare)]))
    print(f"Zero offset: {tare_v * 1e6:.1f} uV  ({tare_v * LBF_PER_VOLT:.2f} lbf)\n")

    # ---- Live plot setup ----
    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 5))
    (line,) = ax.plot([], [], lw=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Force (lbf, tared)")
    ax.set_title("LC103B-3K Load Cell - Force vs Time (live)")
    ax.grid(True)

    def on_key(event):
        if event.key == "m" and times:
            t = times[-1]
            markers.append(t)
            ax.axvline(t, color="gray", linestyle=":", linewidth=1)
            print(f"  Marker {len(markers)} at t = {t:.1f} s")

    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show(block=False)

    # ---- Record ----
    print(f"Recording for up to {TOTAL_SECONDS} s. Close the graph or Ctrl+C to stop early.")
    print("Press 'm' in the graph window to mark when you add a weight.\n")
    n_blocks = int(TOTAL_SECONDS / BLOCK_TIME)
    try:
        for i in range(n_blocks):
            if not plt.fignum_exists(fig.number):
                print("Graph window closed - stopping.")
                break

            v = read_block(task)
            t = (i + 1) * BLOCK_TIME
            f = SIGN * (v - tare_v) * LBF_PER_VOLT
            times.append(t)
            volts.append(v)
            forces.append(f)

            if i % 2 == 0:  # refresh the graph 5 times per second
                line.set_data(times, forces)
                ax.relim()
                ax.autoscale_view()
                plt.pause(0.001)

            if i % 10 == 0:  # print once per second
                print(f"t = {t:6.1f} s | {v * 1e6:8.1f} uV | {f:8.2f} lbf")
    except KeyboardInterrupt:
        print("\nStopped manually.")

if not forces:
    raise SystemExit("No data recorded.")

# ---- Summary ----
forces_arr = np.array(forces)
print("\n--- Summary ---")
print(f"Duration: {times[-1]:.1f} s, {len(forces)} points")
print(f"Min / Max force: {forces_arr.min():.2f} / {forces_arr.max():.2f} lbf")
first_sec = forces_arr[: int(1 / BLOCK_TIME)]
print(f"Noise in first second (std dev): {first_sec.std():.2f} lbf")
if markers:
    print("Markers at: " + ", ".join(f"{m:.1f} s" for m in markers))

stamp = f"{datetime.now():%Y%m%d_%H%M%S}"

# ---- Save CSV ----
csv_name = f"load_cell_time_{stamp}.csv"
with open(csv_name, "w", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["time_s", "voltage_V", "force_lbf"])
    writer.writerows(zip(times, volts, forces))
print(f"Saved data to {csv_name}")

# ---- Final graph ----
plt.ioff()
if not plt.fignum_exists(fig.number):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.grid(True)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Force (lbf, tared)")
    for m in markers:
        ax.axvline(m, color="gray", linestyle=":", linewidth=1)
    (line,) = ax.plot([], [], lw=1.5)

line.set_data(times, forces)
ax.relim()
ax.autoscale_view()
ax.set_title(
    f"LC103B-3K Load Cell - Force vs Time  "
    f"(zero offset {tare_v * 1e6:.1f} µV, peak {forces_arr.max():.1f} lbf)"
)
fig.tight_layout()

png_name = f"load_cell_time_{stamp}.png"
fig.savefig(png_name, dpi=150)
print(f"Saved graph to {png_name}")
plt.show()