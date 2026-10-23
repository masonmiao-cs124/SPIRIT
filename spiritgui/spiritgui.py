from dataclasses import dataclass, field
import threading
from nicegui import ui
import nidaqmx


@dataclass
class _AiTask:
    channel_names: list[str]
    units: list[str]
    values: list[float | None]    # None until the first samples arrive
    lock: threading.Lock = field(default_factory=threading.Lock)


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
        self._ai_task_data[task.name] = _AiTask(
            channel_names=task.ai_channels.channel_names,
            units=units,
            values=[None]*task.number_of_channels
        )

    # only accepting one sample per channel
    def update_ai_task_values(self, task_name: str, values: list[float]) -> None:
        with self._ai_task_data[task_name].lock:
            self._ai_task_data[task_name].values = values

    # The DAQ script using SpiritGui should write to the DAQ the start-state/initial values itself, as usual.
    # For digital output tasks tracked by SpiritGui, the DAQ script should write nothing else to them afterwards, since the DAQ writes happen when the GUI's valve_switches are flipped.
    def add_do_task(self, task: nidaqmx.Task, start_state_values: list[bool]) -> None:
        self._do_task_data[task.name] = _DoTask(
            task=task,
            channel_names=task.do_channels.channel_names,
            values=start_state_values,
        )

    def start(self) -> None:
        ui.run(title="SPIRIT", root=self._build_page, reload=False)

    # -------------------------------------- internal: for the browser page
    def _build_page(self) -> None:
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
                # Update every opened tab (with digital output changes)
                for channel_name, current_value in zip(do_task.channel_names, do_task.values):
                    valve_switches[channel_name].value = current_value

        ui.timer(self.REFRESH_INTERVAL_S, refresh_gui)

    # Called from the switch handler
    def _update_do_channel_value(self, do_task: _DoTask, task_idx: int, is_open: bool) -> None:
        if do_task.values[task_idx] != is_open:
            do_task.values[task_idx] = is_open
            do_task.task.write(do_task.values)