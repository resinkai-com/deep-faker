"""Deep Faker - Python-Native Event Mocking Library."""

from .actions import AddDecay, Context, NewEvent, Select, SetState
from .base import BaseEvent, Entity, Field, StateField
from .outputs import FileOutput, KafkaOutput, MySQLOutput, StdOutOutput
from .simulation import Simulation

__version__ = "0.0.1"

__all__ = [
    "BaseEvent",
    "Field",
    "Entity",
    "StateField",
    "Context",
    "NewEvent",
    "AddDecay",
    "Select",
    "SetState",
    "Simulation",
    "StdOutOutput",
    "FileOutput",
    "KafkaOutput",
    "MySQLOutput",
]


def main() -> None:
    print("Hello from deep-faker!")
