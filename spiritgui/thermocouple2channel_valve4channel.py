"""Thermocouple live display plus valve switches in one SpiritGui window: the
two thermocouple channels of thermocouple2channel.py, read for TOTAL_SECONDS
in a background thread, and one on-demand digital-output task whose channels
the GUI's switches drive.

Analog input: cDAQ1Mod1/ai0 and ai1 (simulated NI 9213), hardware-timed at
AI_TASK_0_SAMPLE_RATE, one sample per channel per read.
Digital output: cDAQ1Mod2/port0/line0 to line3 (simulated NI 9476), one
channel per valve, named by P&ID label; sv_01 to sv_04 are the channels.toml
placeholders until the real tags are known.

SpiritGui does not write start states. This script writes them itself, once,
before it starts the task, and writes nothing else afterwards: every later
write comes from the GUI's switches.
"""
import threading
import time
import nidaqmx
from nidaqmx.constants import (
    ThermocoupleType,
    CJCSource,
    ADCTimingMode,
    AcquisitionType,
    LineGrouping,
)
from spiritgui import SpiritGui

# ------------------------------------------------------------- analog input
AI_TASK_0_PHYSICAL_CHANNELS = ["cDAQ1Mod1/ai0","cDAQ1Mod1/ai1"]
AI_TASK_0_CHANNEL_NAMES = ["tc0","tc1"] # P&ID labels, or whatever name you want showing up on the GUI
AI_TASK_0_CHANNEL_UNITS = ["°C","°C"]
AI_TASK_0_SAMPLE_RATE = 10.0
TOTAL_SECONDS = 30

# ----------------------------------------------------------- digital output
DO_TASK_0_PHYSICAL_CHANNELS = ["cDAQ1Mod2/port0/line0","cDAQ1Mod2/port0/line1","cDAQ1Mod2/port0/line2","cDAQ1Mod2/port0/line3"]
DO_TASK_0_CHANNEL_NAMES = ["sv0","sv1","sv2","bv0"]
DO_TASK_0_START_STATES = [False, True, False, False]  # True = Open; False = Closed

def acquire(update_gui_ai_channel_value):
    """Read both thermocouples for TOTAL_SECONDS, calling update_gui_ai_channel_value(channel_name, temperature) per reading."""
    with nidaqmx.Task() as task:
        channels = task.ai_channels.add_ai_thrmcpl_chan(
            ", ".join(AI_TASK_0_PHYSICAL_CHANNELS),
            thermocouple_type=ThermocoupleType.T,
            cjc_source=CJCSource.BUILT_IN,
        )

        # Faster conversion, with less filtering/noise rejection.
        # Applies to both channels (the NI-9213 shares one ADC across channels).
        channels.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED

        # Configure actual hardware-timed sampling.
        task.timing.cfg_samp_clk_timing(
            rate=AI_TASK_0_SAMPLE_RATE,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=10,
        )

        print(f"Starting acquisition at {AI_TASK_0_SAMPLE_RATE} samples/second...")
        task.start()
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < TOTAL_SECONDS:
            # No time.sleep(): this blocks until the next hardware sample.
            # With two channels, read() returns [[ai0_value], [ai1_value]].
            sample = task.read(
                number_of_samples_per_channel=1,
                timeout=2.0,
            )
            readings = [channel_data[0] for channel_data in sample]

            elapsed = time.perf_counter() - start_time
            for channel_name, temperature in zip(AI_TASK_0_CHANNEL_NAMES, readings):
                update_gui_ai_channel_value(channel_name, temperature)

            # print(
            #     f"Time: {elapsed:.1f}s | "
            #     + " | ".join(
            #         f"{label}: {temperature:.2f} °C"
            #         for label, temperature in zip(AI_TASK_0_CHANNEL_NAMES, readings)
            #     )
            # )
    print("Acquisition finished.")


def open_valve_task(gui: SpiritGui) -> nidaqmx.Task:
    """Create one DO task with one channel per valve, write the start states,
    start the task and register it with the GUI."""
    task = nidaqmx.Task()
    task.do_channels.add_do_chan(
        ", ".join(DO_TASK_0_PHYSICAL_CHANNELS),
        name_to_assign_to_lines=", ".join(DO_TASK_0_CHANNEL_NAMES),
        line_grouping=LineGrouping.CHAN_PER_LINE,
    )
    task.write(DO_TASK_0_START_STATES)  # the only write this script makes; one per channel, in order of adding to the task
    task.start()
    gui.add_do_task(task, DO_TASK_0_START_STATES)
    # print(task_name, "started with", dict(zip(valves, DO_TASK_0_START_STATES)))
    return task

if __name__ == "__main__":
    gui = SpiritGui()
    for units, channel_name in zip(AI_TASK_0_CHANNEL_UNITS, AI_TASK_0_CHANNEL_NAMES):
        gui.add_ai_channel(units, channel_name)

    # Valves first, so they are in their start state before anything else runs.
    with open_valve_task(gui):
        threading.Thread(
            target=acquire, args=(gui.update_ai_value,), daemon=True
        ).start()
        gui.start()  # blocks until Ctrl+C; the valve task closes when the block ends