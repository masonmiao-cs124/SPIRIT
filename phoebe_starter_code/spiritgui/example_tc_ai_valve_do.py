"""Example DAQ script using SpiritGui: two thermocouples' values displayed live and four
valves controlled via switches.

Analog input: cDAQ1Mod1/ai0 and ai1 (NI 9213), one hardware-timed
task at AI_TASK_0_SAMPLE_RATE, read in its own thread, one sample per channel
per read.
Digital output: cDAQ1Mod2/port0/line0 to line3 (NI 9476), one
on-demand task, one channel/line per valve

This script writes the valve/digital-output task's start states itself, once, before they're added to / tracked by SpiritGui.
Every later DAQ digital-output write for this task comes from the GUI's switches.

To add a sensor or valve: add its physical channel, P&ID label, and units or start state to the lists below, at the same position in each list.
To add a task: initialize it in initialize_tasks(), register it with the GUI,
start it, and (analog input) give it its own data_acquisition thread.
"""
import threading
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
# One entry per channel, at the same position in every list: the task's channel order.
AI_TASK_0_PHYSICAL_CHANNELS = ["cDAQ1Mod1/ai0","cDAQ1Mod1/ai1"]
AI_TASK_0_CHANNEL_NAMES = ["tc0","tc1"]  # P&ID labels, or whatever name you want showing up on the GUI
AI_TASK_0_CHANNEL_UNITS = ["°C","°C"]   # shown on the GUI, after the values
AI_TASK_0_SAMPLE_RATE = 100  # samples per second, per channel

# ----------------------------------------------------------- digital output (valves)
# One entry per channel, at the same position in every list: the task's channel/line order.
DO_TASK_0_PHYSICAL_CHANNELS = ["cDAQ1Mod2/port0/line0","cDAQ1Mod2/port0/line1","cDAQ1Mod2/port0/line2","cDAQ1Mod2/port0/line3"]
DO_TASK_0_CHANNEL_NAMES = ["sv0","sv1","sv2","bv0"]
DO_TASK_0_START_STATES = [False, True, False, False]  # True = Open; False = Closed

def data_acquisition(ai_task, gui_update_ai_task_values, stop_data_acquisition):
    """Reads the input task until stop_data_acquisition is set, and (currently) hands every read to the GUI.
    Runs in its own thread, one per input task, because read() blocks until the task's next sample.

    Args:
        ai_task::nidaqmx.Task
            The initialized, registered (with SpiritGui), and started analog-input task to read.
        gui_update_ai_task_values::callable
            SpiritGui.update_ai_task_values; called with the task's name and one sample per channel.
        stop_data_acquisition::threading.Event
            Set by the main block after Ctrl+C; ends the while loop after the current DAQ read.
    """
    while not stop_data_acquisition.is_set():
        sample = ai_task.read(
            number_of_samples_per_channel=1,
            timeout=2.0,
        )
        if ai_task.number_of_channels == 1:
            readings = sample
        else:
            readings = [channel_data[0] for channel_data in sample] # With two channels, read() returns [[ai0_value], [ai1_value]].

        gui_update_ai_task_values(ai_task.name, readings)

    print("Data acquisition finished.")

def initialize_tasks(ai_task_0, do_task_0):
    """Adds channels and timing to tasks, and initializes digital-outputs on the DAQ.
    The tasks are started in the main block after this function returns and after SpiritGui task registration.

    Args:
        ai_task_0::nidaqmx.Task
            Empty task; becomes thermocouple task (in this case).
        do_task_0::nidaqmx.Task
            Empty task; becomes valve task.
    """
    # Initialize analog input task 0
    ai_channels = ai_task_0.ai_channels.add_ai_thrmcpl_chan(
        ", ".join(AI_TASK_0_PHYSICAL_CHANNELS),
        name_to_assign_to_channel=", ".join(AI_TASK_0_CHANNEL_NAMES),
        thermocouple_type=ThermocoupleType.T,
        cjc_source=CJCSource.BUILT_IN,
    )
    ai_channels.ai_adc_timing_mode = ADCTimingMode.HIGH_SPEED   # Faster conversion, with less filtering/noise rejection.
    ai_task_0.timing.cfg_samp_clk_timing(
        rate=AI_TASK_0_SAMPLE_RATE,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=10,
    )

    # Initialize digital output task 0
    do_task_0.do_channels.add_do_chan(
        ", ".join(DO_TASK_0_PHYSICAL_CHANNELS),
        name_to_assign_to_lines=", ".join(DO_TASK_0_CHANNEL_NAMES),
        line_grouping=LineGrouping.CHAN_PER_LINE,
    )
    do_task_0.write(DO_TASK_0_START_STATES)  # the only write this script makes


if __name__ == "__main__":
    gui = SpiritGui()

    with nidaqmx.Task() as ai_task_0, nidaqmx.Task() as do_task_0:  # both tasks close when the block ends
        initialize_tasks(ai_task_0, do_task_0)

        # Register tasks with SpiritGui
        gui.add_ai_task(ai_task_0, AI_TASK_0_CHANNEL_UNITS)
        gui.add_do_task(do_task_0, DO_TASK_0_START_STATES)

        # Start tasks
        ai_task_0.start()
        do_task_0.start()

        stop_data_acquisition = threading.Event()  # set after Ctrl+C; ends the read loop in data_acquisition()
        # Start data acquisition thread (one per analog-input task)
        data_acquisition_thread_ai_task_0 = threading.Thread(
            target=data_acquisition, args=(ai_task_0, gui.update_ai_task_values, stop_data_acquisition), daemon=True
        )
        data_acquisition_thread_ai_task_0.start()

        try:
            gui.start()  # opens GUI page in a browser tab; returns at Ctrl+C
        except KeyboardInterrupt:
            pass
        finally:
            stop_data_acquisition.set()
            data_acquisition_thread_ai_task_0.join()    # waits for the current DAQ read to end
