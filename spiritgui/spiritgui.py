from dataclasses import dataclass, field
import threading
from nicegui import ui
import nidaqmx


@dataclass
class _AiChannel:
    units: str
    value: float | None = None  # None until the first sample arrives
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class _DoChannel:
    task_name: str
    task_idx: int


class SpiritGui:
    REFRESH_INTERVAL_S = 0.1  # seconds between gui refreshes
    VALUE_FORMAT = "{:.2f}"

    def __init__(self) -> None:
        self._ai_channel_data: dict[str, _AiChannel] = {}

        self._do_tasks: dict[str, nidaqmx.Task] = {}
        self._do_task_data: dict[str, list[bool]] = {}
        self._do_channel_data: dict[str, _DoChannel] = {}

    # ----------------------------------------- what the DAQ script using SpiritGui calls
    def add_ai_channel(self, units: str, channel_name: str) -> None:
        self._ai_channel_data[channel_name] = _AiChannel(units=units)

    # Called from the DAQ thread
    def update_ai_value(self, channel_name: str, value: float) -> None:
        with self._ai_channel_data[channel_name].lock:
            self._ai_channel_data[channel_name].value = value

    # The DAQ script using SpiritGui should write to the DAQ the start-state/initial values itself, as usual.
    # For digital output tasks tracked by SpiritGui, the DAQ script should write nothing else to them afterwards, since the DAQ writes happen when the GUI's switches are flipped.
    def add_do_task(self, task: nidaqmx.Task, start_state_values: list[bool]) -> None:
        self._do_tasks[task.name] = task
        self._do_task_data[task.name] = start_state_values

        for idx, channel in enumerate(task.do_channels):
            self._do_channel_data[channel.name] = _DoChannel(
                task_name=task.name,
                task_idx=idx,
            )

    def start(self) -> None:
        ui.run(title="SPIRIT", root=self._build_page, reload=False)

    # -------------------------------------- internal: for the browser page
    def _build_page(self) -> None:
        value_labels: dict[str, ui.label] = {}
        for channel_name, data in self._ai_channel_data.items():
            with ui.row().classes("items-center gap-2"):
                ui.label(f"{channel_name}:").classes("font-bold")
                value_labels[channel_name] = ui.label("--")
                ui.label(data.units)

        switches: dict[str, ui.switch] = {}
        for channel_name, data in self._do_channel_data.items():
            switches[channel_name] = ui.switch(
                channel_name,
                value=self._do_task_data[data.task_name][data.task_idx],
                on_change=lambda e, name=channel_name: self._update_do_value(
                    name, e.value
                ),
            )

        def refresh_gui() -> None:    # Timer callback
            for channel_name, value_label in value_labels.items():
                with self._ai_channel_data[channel_name].lock:
                    current_value = self._ai_channel_data[channel_name].value
                value_label.text = (
                    "--" if current_value is None
                    else self.VALUE_FORMAT.format(current_value)
                )

            for channel_name, switch in switches.items():
                # Update every opened tab (with digital output changes)
                task_name = self._do_channel_data[channel_name].task_name
                task_idx = self._do_channel_data[channel_name].task_idx
                switch.value = self._do_task_data[task_name][task_idx]

        ui.timer(self.REFRESH_INTERVAL_S, refresh_gui)

    # Called from the switch handler
    def _update_do_value(self, channel_name: str, is_open: bool) -> None:
        task_name = self._do_channel_data[channel_name].task_name
        task_idx = self._do_channel_data[channel_name].task_idx

        if self._do_task_data[task_name][task_idx] != is_open:
            self._do_task_data[task_name][task_idx] = is_open
            self._do_tasks[task_name].write(self._do_task_data[task_name])
            if is_open:
                print(channel_name, "is now OPEN")
            else:
                print(channel_name, "is now CLOSED")
