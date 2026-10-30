from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import count
from typing import Any, ClassVar


class PortKind(StrEnum):
    PROCESS = "process"
    SIGNAL = "signal"


@dataclass(slots=True, frozen=True)
class Port:
    id: str
    side: str
    kind: PortKind = PortKind.PROCESS
    max_connections: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "side": self.side,
            "kind": self.kind.value,
            "max_connections": self.max_connections,
        }


@dataclass(slots=True)
class PidComponent:
    id: str
    tag: str
    x: float
    y: float
    title: str
    channel: str | None = None
    value: float | str | None = None
    units: str = ""
    quality: str = "good"
    notes: str = ""
    rotation: int = 0

    kind: ClassVar[str] = "component"
    port_specs: ClassVar[tuple[Port, ...]] = ()

    def ports(self) -> list[Port]:
        return list(self.port_specs)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "tag": self.tag,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "channel": self.channel,
            "value": self.value,
            "units": self.units,
            "quality": self.quality,
            "notes": self.notes,
            "ports": [port.as_dict() for port in self.ports()],
        }


@dataclass(slots=True)
class PressureTransducer(PidComponent):
    kind: ClassVar[str] = "pressure_transducer"
    port_specs: ClassVar[tuple[Port, ...]] = (
        Port("process", "right", max_connections=3),
    )


@dataclass(slots=True)
class Thermocouple(PidComponent):
    kind: ClassVar[str] = "thermocouple"
    port_specs: ClassVar[tuple[Port, ...]] = (
        Port("process", "left", max_connections=3),
    )


@dataclass(slots=True)
class SolenoidValve(PidComponent):
    kind: ClassVar[str] = "solenoid_valve"
    port_specs: ClassVar[tuple[Port, ...]] = (
        Port("top", "top", max_connections=3),
        Port("bottom", "bottom", max_connections=3),
        Port("left", "left", max_connections=3),
        Port("right", "right", max_connections=3),
    )

    commanded_open: bool = False
    safe_state_open: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = PidComponent.as_dict(self)
        data["commanded_open"] = self.commanded_open
        data["safe_state_open"] = self.safe_state_open
        data["value"] = "OPEN" if self.commanded_open else "CLOSED"
        data["units"] = ""
        return data


@dataclass(slots=True)
class Tank(PidComponent):
    kind: ClassVar[str] = "tank"
    port_specs: ClassVar[tuple[Port, ...]] = (
        Port("top", "top", max_connections=4),
        Port("bottom", "bottom", max_connections=2),
        Port("left", "left", max_connections=3),
        Port("right", "right", max_connections=3),
    )


@dataclass(slots=True)
class Connection:
    id: str
    source_component: str
    source_port: str
    target_component: str
    target_port: str
    medium: str = "pressurant"

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "source_component": self.source_component,
            "source_port": self.source_port,
            "target_component": self.target_component,
            "target_port": self.target_port,
            "medium": self.medium,
        }


@dataclass(slots=True)
class PidGraph:
    components: dict[str, PidComponent] = field(default_factory=dict)
    connections: dict[str, Connection] = field(default_factory=dict)
    _connection_counter: count = field(default_factory=lambda: count(1), repr=False)

    def add_component(self, component: PidComponent) -> None:
        if component.id in self.components:
            raise ValueError(f"Duplicate component ID: {component.id}")
        self.components[component.id] = component

    def add_connection(
        self,
        source_component: str,
        source_port: str,
        target_component: str,
        target_port: str,
    ) -> Connection:
        connection = Connection(
            id=f"pipe-{next(self._connection_counter)}",
            source_component=source_component,
            source_port=source_port,
            target_component=target_component,
            target_port=target_port,
        )
        self.connections[connection.id] = connection
        return connection

    def component_payload(self) -> list[dict[str, Any]]:
        return [component.as_dict() for component in self.components.values()]

    def connection_payload(self) -> list[dict[str, str]]:
        return [connection.as_dict() for connection in self.connections.values()]


def introductory_graph() -> PidGraph:
    graph = PidGraph()

    graph.add_component(
        Tank(
            id="tank-gn2",
            tag="T3-GN2-ACT",
            title="GN₂ supply tank",
            x=450,
            y=500,
            value=2900,
            units="psig",
            notes="Pressurant supply",
        )
    )
    graph.add_component(
        SolenoidValve(
            id="sv-gn2",
            tag="SV1-GN2-ACT",
            title="GN₂ isolation solenoid",
            x=450,
            y=280,
            channel="cDAQ1Mod2/port0/line0",
            commanded_open=False,
            safe_state_open=False,
            notes="Prototype display only; no hardware command is issued",
        )
    )
    graph.add_component(
        PressureTransducer(
            id="pt-low",
            tag="PT5-GN2-ACT",
            title="Tank pressure transducer",
            x=265,
            y=405,
            channel="cDAQ1Mod4/ai0",
            value=2886.4,
            units="psig",
            notes="0–3000 psig",
        )
    )
    graph.add_component(
        PressureTransducer(
            id="pt-high",
            tag="PT6-GN2-ACT",
            title="Downstream pressure transducer",
            x=265,
            y=165,
            channel="cDAQ1Mod4/ai2",
            value=0.0,
            units="psig",
            notes="Downstream of the isolation valve",
        )
    )
    graph.add_component(
        Thermocouple(
            id="tc-tank",
            tag="TC1-GN2-ACT",
            title="Tank temperature",
            x=635,
            y=405,
            channel="cDAQ1Mod1/ai0",
            value=22.6,
            units="°C",
            notes="Type T thermocouple",
        )
    )

    graph.add_connection("tank-gn2", "top", "sv-gn2", "bottom")
    graph.add_connection("pt-low", "process", "tank-gn2", "top")
    graph.add_connection("sv-gn2", "top", "pt-high", "process")
    graph.add_connection("tank-gn2", "top", "tc-tank", "process")
    return graph

