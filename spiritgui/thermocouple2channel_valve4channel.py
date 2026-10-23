"""Thermocouple live display plus valve switches in one SpiritGui window: the
two thermocouple channels of thermocouple2channel.py, read in a background thread, and one on-demand digital-output task whose channels
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
AI_TASK_0_SAMPLE_RATE = 100

# ----------------------------------------------------------- digital output
DO_TASK_0_PHYSICAL_CHANNELS = ["cDAQ1Mod2/port0/line0","cDAQ1Mod2/port0/line1","cDAQ1Mod2/port0/line2","cDAQ1Mod2/port0/line3"]
DO_TASK_0_CHANNEL_NAMES = ["sv0","sv1","sv2","bv0"]
DO_TASK_0_START_STATES = [False, True, False, False]  # True = Open; False = Closed

def data_acquisition(ai_task_0,update_gui_ai_channel_value, stop_data_acquisition):
    while not stop_data_acquisition.is_set():
        # No time.sleep(): this blocks until the next hardware sample.
        # With two channels, read() returns [[ai0_value], [ai1_value]].
        sample = ai_task_0.read(
            number_of_samples_per_channel=1,
            timeout=2.0,
        )
        readings = [channel_data[0] for channel_data in sample]

        for channel_name, temperature in zip(AI_TASK_0_CHANNEL_NAMES, readings):
            update_gui_ai_channel_value(channel_name, temperature)

    print("Data acquisition finished.")

def initialize_and_start_tasks(ai_task_0, do_task_0):
    # Initialize tasks
    channels = ai_task_0.ai_channels.add_ai_thrmcpl_chan(
        ", ".join(AI_TASK_0_PHYSICAL_CHANNELS),
        thermocouple_type=ThermocoupleType.T,
        cjc_source=CJCSource.BUILT_IN,
    )
    # Faster conversion, with less filtering/noise rejection.
    # Applies to both channels (the NI-9213 shares one ADC across channels).
    channels.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED
    # Configure actual hardware-timed sampling.
    ai_task_0.timing.cfg_samp_clk_timing(
        rate=AI_TASK_0_SAMPLE_RATE,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=10,
    )

    # print(f"Starting acquisition at {AI_TASK_0_SAMPLE_RATE} samples/second...")

    do_task_0.do_channels.add_do_chan(
            ", ".join(DO_TASK_0_PHYSICAL_CHANNELS),
            name_to_assign_to_lines=", ".join(DO_TASK_0_CHANNEL_NAMES),
            line_grouping=LineGrouping.CHAN_PER_LINE,
        )
    do_task_0.write(DO_TASK_0_START_STATES)  # the only write this script makes; one per channel, in order of adding to the task
    
    # Start tasks
    ai_task_0.start()
    do_task_0.start()


if __name__ == "__main__":
    with nidaqmx.Task() as ai_task_0, nidaqmx.Task() as do_task_0:
        initialize_and_start_tasks(ai_task_0,do_task_0)

        gui = SpiritGui()
        gui.add_do_task(do_task_0, DO_TASK_0_START_STATES)
        for units, channel_name in zip(AI_TASK_0_CHANNEL_UNITS, AI_TASK_0_CHANNEL_NAMES):
            gui.add_ai_channel(units, channel_name)

        stop_data_acquisition = threading.Event() # set after Ctrl+C; ends the read loop in data_acquisition()
        data_acquisition_thread = threading.Thread(
            target=data_acquisition, args=(ai_task_0,gui.update_ai_value,stop_data_acquisition), daemon=True
        )
        data_acquisition_thread.start()

        try:
            gui.start()  # blocks until Ctrl+C
        except KeyboardInterrupt:
            pass
        finally:
            stop_data_acquisition.set()
            data_acquisition_thread.join()

