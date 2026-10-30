from __future__ import annotations

from itertools import count
from random import uniform

from nicegui import ui

from components import PressureTransducer, SolenoidValve, Tank, Thermocouple, introductory_graph
from pid_canvas import PidCanvas


ui.add_css(
    """
    body {
        background: #f4f6f8;
        color: #17202a;
    }
    .pid-page {
        width: min(1180px, calc(100vw - 32px));
        margin: 0 auto;
    }
    .pid-toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        width: 100%;
    }
    .pid-canvas {
        width: 100%;
        display: block;
    }
    .pid-canvas-root {
        position: relative;
        width: 100%;
        background: white;
        border: 1px solid #b9c1ca;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 8px 28px rgba(27, 39, 51, 0.08);
    }
    .pid-svg {
        display: block;
        width: 100%;
        min-height: 620px;
        touch-action: none;
        user-select: none;
    }
    .pid-background { fill: #ffffff; }
    .pid-grid-dot { fill: #d9dee5; }
    .pid-pipe {
        fill: none;
        stroke-width: 3;
        stroke-linejoin: round;
        stroke-linecap: square;
        vector-effect: non-scaling-stroke;
    }
    .pid-pipe-pressurant { stroke: #7441c8; }
    .pid-node { cursor: grab; }
    .pid-node-dragging { cursor: grabbing; }
    .pid-symbol,
    .pid-symbol-line,
    .pid-coil {
        fill: #ffffff;
        stroke: #22272b;
        stroke-width: 2.2;
        vector-effect: non-scaling-stroke;
    }
    .pid-valve-body {
        fill: #1f2328;
        stroke: #1f2328;
        stroke-width: 2;
        vector-effect: non-scaling-stroke;
    }
    .pid-node-selected .pid-symbol,
    .pid-node-selected .pid-valve-body,
    .pid-node-selected .pid-coil {
        stroke: #1261a0;
        stroke-width: 3.5;
    }
    .pid-symbol-letter {
        font: 500 22px Arial, sans-serif;
        fill: #1f2328;
    }
    .pid-coil-letter {
        font: 500 10px Arial, sans-serif;
        fill: #1f2328;
    }
    .pid-tank-label {
        font: 500 18px Arial, sans-serif;
        fill: #1f2328;
    }
    .pid-tag {
        font: 500 13px Arial, sans-serif;
        fill: #24292f;
    }
    .pid-reading {
        font: 12px Arial, sans-serif;
        fill: #57606a;
    }
    .pid-port {
        fill: #ffffff;
        stroke: #1261a0;
        stroke-width: 2;
        opacity: 0;
        cursor: crosshair;
        vector-effect: non-scaling-stroke;
    }
    .pid-node:hover .pid-port,
    .pid-port-pending {
        opacity: 1;
    }
    .pid-port-pending {
        fill: #1261a0;
    }
    .pid-tooltip {
        position: absolute;
        z-index: 5;
        width: 250px;
        padding: 12px 14px;
        border-radius: 7px;
        background: rgba(24, 29, 35, 0.96);
        color: white;
        font: 13px/1.35 Arial, sans-serif;
        pointer-events: none;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    }
    .pid-tooltip-title {
        margin-bottom: 2px;
        font-weight: 600;
    }
    .pid-tooltip dl {
        display: grid;
        grid-template-columns: 62px 1fr;
        gap: 3px 8px;
        margin: 9px 0 0;
    }
    .pid-tooltip dt { color: #aeb9c5; }
    .pid-tooltip dd { margin: 0; overflow-wrap: anywhere; }
    .pid-tooltip-note {
        margin-top: 8px;
        padding-top: 7px;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
        color: #d8dee4;
    }
    .pid-canvas-hint {
        position: absolute;
        left: 12px;
        bottom: 10px;
        padding: 5px 8px;
        border-radius: 4px;
        background: rgba(255, 255, 255, 0.88);
        color: #57606a;
        font-size: 12px;
        pointer-events: none;
    }
    """,
    shared=True,
)


graph = introductory_graph()
tag_counters = {
    "pressure_transducer": count(7),
    "thermocouple": count(2),
    "solenoid_valve": count(2),
    "tank": count(4),
}


def next_position() -> tuple[float, float]:
    item_count = len(graph.components)
    return 120 + (item_count % 5) * 155, 120 + ((item_count // 5) % 3) * 175


@ui.page("/")
def index() -> None:
    selected = ui.label("Select a component to inspect it.").classes("text-sm text-gray-600")

    def show_selected(component) -> None:
        value = component.value
        if isinstance(component, SolenoidValve):
            value = "OPEN" if component.commanded_open else "CLOSED"
        suffix = f" {component.units}" if component.units else ""
        selected.set_text(f"Selected: {component.tag} · {component.title} · {value}{suffix}")

    with ui.column().classes("pid-page gap-3 py-4"):
        with ui.row().classes("w-full items-end justify-between gap-4"):
            with ui.column().classes("gap-0"):
                ui.label("SPIRIT live P&ID prototype").classes("text-2xl font-semibold")
                ui.label("GN₂ pressurant subsystem · hover for details").classes("text-sm text-gray-600")
            edit_switch = ui.switch("Edit mode", value=True)

        with ui.row().classes("pid-toolbar"):
            ui.label("Add component:").classes("font-medium")

            canvas_holder: dict[str, PidCanvas] = {}

            def add_component(kind: str) -> None:
                x, y = next_position()
                number = next(tag_counters[kind])
                if kind == "pressure_transducer":
                    component = PressureTransducer(
                        id=f"pt-{number}", tag=f"PT{number}-GN2-ACT", title="Pressure transducer",
                        x=x, y=y, value=0.0, units="psig", notes="Unassigned prototype component",
                    )
                elif kind == "thermocouple":
                    component = Thermocouple(
                        id=f"tc-{number}", tag=f"TC{number}-GN2-ACT", title="Thermocouple",
                        x=x, y=y, value=22.0, units="°C", notes="Type T prototype component",
                    )
                elif kind == "solenoid_valve":
                    component = SolenoidValve(
                        id=f"sv-{number}", tag=f"SV{number}-GN2-ACT", title="Normally closed solenoid valve",
                        x=x, y=y, commanded_open=False, safe_state_open=False,
                        notes="Prototype display only; no hardware command is issued",
                    )
                else:
                    component = Tank(
                        id=f"tank-{number}", tag=f"T{number}-GN2-ACT", title="GN₂ tank",
                        x=x, y=y, value=0.0, units="psig", notes="Prototype vessel",
                    )
                canvas_holder["canvas"].add_component(component)

            ui.button("Pressure transducer", icon="speed", on_click=lambda: add_component("pressure_transducer")).props("outline")
            ui.button("Thermocouple", icon="device_thermostat", on_click=lambda: add_component("thermocouple")).props("outline")
            ui.button("Solenoid valve", icon="toggle_on", on_click=lambda: add_component("solenoid_valve")).props("outline")
            ui.button("Tank", icon="propane_tank", on_click=lambda: add_component("tank")).props("outline")

        canvas = PidCanvas(graph, on_selected=show_selected)
        canvas_holder["canvas"] = canvas
        edit_switch.on_value_change(lambda event: canvas.set_editable(bool(event.value)))
        selected

        simulation_enabled = ui.switch("Simulate changing sensor values", value=False)

        def update_simulation() -> None:
            if not simulation_enabled.value:
                return
            canvas.set_component_state("pt-low", value=2886.4 + uniform(-3.0, 3.0))
            canvas.set_component_state("pt-high", value=max(0.0, uniform(-0.3, 0.3)))
            canvas.set_component_state("tc-tank", value=22.6 + uniform(-0.15, 0.15))

        ui.timer(0.5, update_simulation)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="SPIRIT live P&ID", port=8081, reload=False)

