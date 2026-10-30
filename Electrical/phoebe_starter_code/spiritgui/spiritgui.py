"""Builds a browser page for a DAQ script: live analog-input values and switches for the
digital-output valves.

Per task, SpiritGui keeps one list of values.
Analog-input values arrive from the DAQ script's read/data_acquisition threads through update_ai_task_values().
Digital-output values go to the DAQ with _update_do_channel_value() when a switch is flipped.

A DAQ script uses SpiritGui in this order:
    gui = SpiritGui()                       # one per program (ui.run() serves one page)
    gui.add_ai_task(task, units)            # after the task is initialized in the DAQ script
    gui.add_do_task(task, start_states)     # after the task is initialized in the DAQ script
        Note: The DAQ script using SpiritGui should write to the DAQ the start-state/
        initial values itself, as usual. For digital output tasks tracked by
        SpiritGui, the DAQ script should write nothing else to them afterwards.
    gui.start()                             # opens the page in a browser tab; returns at Ctrl+C
with one read/data_acquisition thread per analog-input task calling gui.update_ai_task_values().

Refer to example_tc_ai_valve_do.py for an example DAQ script.
"""
from dataclasses import dataclass, field
import threading
from nicegui import ui
import nidaqmx


@dataclass
class _AiTask:
    channel_names: list[str]
    values: list[float | None]    # None until the first samples arrive
    units: list[str]
    lock: threading.Lock = field(default_factory=threading.Lock)    # Needed for values: set by the DAQ thread, read by the page timer


@dataclass
class _DoTask:
    task: nidaqmx.Task  # written to when one of its switches is flipped
    channel_names: list[str]
    values: list[bool]


class SpiritGui:
    REFRESH_INTERVAL_S = 0.1  # seconds between gui refreshes
    VALUE_FORMAT = "{:.2f}"

    def __init__(self) -> None:
        self._ai_task_data: dict[str, _AiTask] = {}
        self._do_task_data: dict[str, _DoTask] = {}

    # ----------------------------------------- what the DAQ script using SpiritGui calls
    def add_ai_task(self, task: nidaqmx.Task, units: list[str]) -> None:
        """Shows the task's channels' values live.

        Args:
            task::nidaqmx.Task
                The analog-input task, with its channels already added (in the DAQ script). SpiritGui uses its virtual channel names.
            units::list[str]
                One per channel
        """
        self._ai_task_data[task.name] = _AiTask(
            channel_names=task.ai_channels.channel_names,
            values=[None]*task.number_of_channels,
            units=units,
        )

    def update_ai_task_values(self, task_name: str, values: list[float]) -> None:
        """Takes one sample (per channel) of a task. Called from the DAQ script's read/data_acquisition thread.

        Args:
            task_name::str
                task.name of a task given to add_ai_task().
            values::list[float]
                One value per channel
        """
        with self._ai_task_data[task_name].lock:
            self._ai_task_data[task_name].values = values

    def add_do_task(self, task: nidaqmx.Task, start_state_values: list[bool]) -> None:
        """Shows the task's channels as switches.

        Args:
            task::nidaqmx.Task
                The digital-output task, with its channels/lines already added and the start states already written (in the DAQ script). SpiritGui uses its virtual channel/line names as its switch labels.
            start_state_values::list[bool]
                One True/False (Open/Closed) state per channel/line.
                The list the DAQ script used to initialize the task.
        """
        self._do_task_data[task.name] = _DoTask(
            task=task,
            channel_names=task.do_channels.channel_names,
            values=start_state_values,
        )

    def start(self) -> None:
        """Serves the page and opens it in a browser tab; returns at Ctrl+C."""
        #ui.run(title="SPIRIT", root=self._build_page, reload=False)
        ui.run(
            title="SPIRIT",
            root=self._build_page,
            reload=False,
            port=8081,
        )

    # -------------------------------------- internal: for the browser page
    def _build_page(self) -> None:
        """Builds the page: one row per analog-input channel, one switch per digital-output channel/line, and a timer that keeps the tabs updated with the values stored in SpiritGui."""
        sensor_data_labels: dict[str, ui.label] = {}
        for ai_task in self._ai_task_data.values():
            for channel_name, units in zip(ai_task.channel_names, ai_task.units):
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{channel_name}:").classes("font-bold")
                    sensor_data_labels[channel_name] = ui.label("--")
                    ui.label(units)

        valve_switches: dict[str, ui.switch] = {}
        for do_task in self._do_task_data.values():
            for task_idx, (channel_name, value) in enumerate(zip(do_task.channel_names, do_task.values)):
                valve_switches[channel_name] = ui.switch(
                    channel_name,
                    value=value,
                    on_change=lambda e, do_task=do_task, task_idx=task_idx: self._update_do_channel_value(
                        do_task, task_idx, e.value
                    ),
                )

        def refresh_gui() -> None:    # Timer callback
            for ai_task in self._ai_task_data.values():
                with ai_task.lock:
                    current_values = ai_task.values

                for channel_name, current_value in zip(ai_task.channel_names, current_values):
                    sensor_data_labels[channel_name].text = (
                        "--" if current_value is None
                        else self.VALUE_FORMAT.format(current_value)
                    )

            for do_task in self._do_task_data.values():
                # Update every opened tab (with updated digital output values)
                for channel_name, current_value in zip(do_task.channel_names, do_task.values):
                    valve_switches[channel_name].value = current_value

        ui.timer(self.REFRESH_INTERVAL_S, refresh_gui)

    def _update_do_channel_value(self, do_task: _DoTask, task_idx: int, is_open: bool) -> None:
        """Switch handler: writes to the DAQ when a switch changed its channel/line's state/value.

        Args:
            do_task::_DoTask
                The task the switch belongs to.
            task_idx::int
                The switch's channel/line's position in the task.
            is_open::bool
                The switch's new value (True = open, False = closed)
        """
        if do_task.values[task_idx] != is_open:
            do_task.values[task_idx] = is_open
            do_task.task.write(do_task.values)