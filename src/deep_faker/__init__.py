"""Deep Faker - Python-Native Event Mocking Library."""

from .actions import (
    AddDecay,
    Context,
    FlowContext,
    GlobalContext,
    NewEvent,
    Select,
    SetState,
)
from .base import BaseEvent, Entity, Field, StateField
from .entity_manager import EntityManager
from .outputs import FileOutput, KafkaOutput, MySQLOutput, StdOutOutput
from .simulation import Simulation

__version__ = "0.0.1"

__all__ = [
    "BaseEvent",
    "Field",
    "Entity",
    "StateField",
    "EntityManager",
    "Context",  # Legacy - will be deprecated
    "FlowContext",  # New flow context
    "GlobalContext",  # New global context
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
    """Entry point for the CLI."""
    from .cli import main as cli_main

    cli_main()
