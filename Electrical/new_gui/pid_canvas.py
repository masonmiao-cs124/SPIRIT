from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import events
from nicegui.element import Element

from components import Connection, PidComponent, PidGraph


class PidCanvas(Element, component="pid_canvas.js", default_classes="pid-canvas"):
    def __init__(
        self,
        graph: PidGraph,
        *,
        on_selected: Callable[[PidComponent], None] | None = None,
    ) -> None:
        super().__init__()
        self.graph = graph
        self._on_selected_callback = on_selected
        self._props["components"] = graph.component_payload()
        self._props["connections"] = graph.connection_payload()
        self._props["editable"] = True

        self.on("component-moved", self._handle_component_moved)
        self.on("component-selected", self._handle_component_selected)
        self.on("connection-created", self._handle_connection_created)

    def _handle_component_moved(self, event: events.GenericEventArguments) -> None:
        component = self.graph.components[event.args["id"]]
        component.x = float(event.args["x"])
        component.y = float(event.args["y"])

    def _handle_component_selected(self, event: events.GenericEventArguments) -> None:
        component = self.graph.components[event.args["id"]]
        if self._on_selected_callback:
            self._on_selected_callback(component)

    def _handle_connection_created(self, event: events.GenericEventArguments) -> None:
        connection = Connection(
            id=event.args["id"],
            source_component=event.args["source_component"],
            source_port=event.args["source_port"],
            target_component=event.args["target_component"],
            target_port=event.args["target_port"],
        )
        self.graph.connections[connection.id] = connection

    def add_component(self, component: PidComponent) -> None:
        self.graph.add_component(component)
        self.run_method("addComponent", component.as_dict())

    def set_editable(self, editable: bool) -> None:
        self._props["editable"] = editable
        self.update()

    def set_component_state(self, component_id: str, **changes: Any) -> None:
        component = self.graph.components[component_id]
        for name, value in changes.items():
            if hasattr(component, name):
                setattr(component, name, value)
        self.run_method("setComponentState", component_id, changes)

