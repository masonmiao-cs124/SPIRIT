from dataclasses import dataclass, field
import threading
from nicegui import ui

@dataclass
class AiChannel:
    units: str
    pid_label: str
    value: float | None = None  # None until the first sample arrives
    lock: threading.Lock = field(default_factory=threading.Lock)

class SpiritGui:
    REFRESH_INTERVAL_S = 0.1  # seconds between gui refreshes
    VALUE_FORMAT = "{:.2f}"

    def __init__(self) -> None:
        self.ai_channels: dict[str, AiChannel] = {}
        

    def add_ai_channel(self, units: str, pid_label: str, physical_channel: str) -> None:
        self.ai_channels[physical_channel] = AiChannel(
            units=units,
            pid_label=pid_label,
        )

    def update_ai_value(self, physical_channel: str, value: float) -> None:     # Called from the DAQ thread
        with self.ai_channels[physical_channel].lock:
            self.ai_channels[physical_channel].value = value

    def build_page(self) -> None:
        value_labels: dict[str, ui.label] = {}
        for physical_channel, chan in self.ai_channels.items():
            with ui.row().classes("items-center gap-2"):
                ui.label(f"{chan.pid_label}:").classes("font-bold")
                value_labels[physical_channel] = ui.label("--")
                ui.label(chan.units)

        def refresh_ai_gui_labels() -> None:    # Timer callback
            for physical_channel, value_label in value_labels.items():
                with self.ai_channels[physical_channel].lock:
                    current_value = self.ai_channels[physical_channel].value
                value_label.text = (
                    "--" if current_value is None
                    else self.VALUE_FORMAT.format(current_value)
                )

        ui.timer(self.REFRESH_INTERVAL_S, refresh_ai_gui_labels)


    def start(self) -> None:
        ui.run(title="SPIRIT", root=self.build_page, reload=False)

    # def add_do_chan(self):



