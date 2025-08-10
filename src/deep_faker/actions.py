"""Action classes for declarative flow definitions."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type

from .base import BaseEvent, Entity


class Context:
    """Context object passed to flows containing current simulation state."""

    def __init__(
        self,
        simulation,
        current_time: datetime,
        selected_entity: Optional[Entity] = None,
        session_id: Optional[str] = None,
    ):
        self.simulation = simulation
        self.current_time = current_time
        self.selected_entity = selected_entity
        self.current_event_data = {}
        # Track entities by type - allows multiple entities per flow
        self.entities_by_type: Dict[Type[Entity], Entity] = {}
        # Session ID for this flow execution
        self.session_id = session_id or str(uuid.uuid4())

        # If we have a selected entity, add it to the entities_by_type
        if selected_entity:
            self.entities_by_type[type(selected_entity)] = selected_entity

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity to the context for this flow."""
        self.entities_by_type[entity_type] = entity

    def get_entity(self, entity_type: Type[Entity]) -> Optional[Entity]:
        """Get an entity of the specified type from the context."""
        return self.entities_by_type.get(entity_type)

    def get_primary_entity(self) -> Optional[Entity]:
        """Get the primary entity (selected or first created)."""
        if self.selected_entity:
            return self.selected_entity
        # Return the first entity if any
        if self.entities_by_type:
            return next(iter(self.entities_by_type.values()))
        return None


class NewEvent:
    """Action to create a new event."""

    def __init__(
        self,
        ctx: Context,
        event_schema: Type[BaseEvent],
        save_entity: Optional[Type[Entity]] = None,
        mutate: Optional["SetState"] = None,
        **field_overrides,
    ):
        self.ctx = ctx
        self.event_schema = event_schema
        self.save_entity = save_entity
        self.mutate = mutate
        self.field_overrides = field_overrides


class AddDecay:
    """Action to advance time with a probability of flow termination."""

    def __init__(self, ctx: Context, rate: float, **kwargs_for_time_delta):
        self.ctx = ctx
        self.rate = rate  # Probability of termination (0.0 to 1.0)
        self.time_delta = timedelta(**kwargs_for_time_delta)


class Select:
    """Action/Filter to select entities based on conditions."""

    def __init__(self, entity_type: Type[Entity], where: Optional[List[tuple]] = None):
        self.entity_type = entity_type
        self.where = where or []

    def matches(self, entity: Entity) -> bool:
        """Check if entity matches the where conditions."""
        for field, operation, value in self.where:
            entity_value = getattr(entity, field, None)

            if operation == "is":
                if entity_value != value:
                    return False
            elif operation == "is_not":
                if entity_value == value:
                    return False
            elif operation == "greater_than":
                if not (entity_value is not None and entity_value > value):
                    return False
            elif operation == "less_than":
                if not (entity_value is not None and entity_value < value):
                    return False
            elif operation == "in":
                if entity_value not in value:
                    return False

        return True


class SetState:
    """Action to update entity state."""

    def __init__(self, entity_type: Type[Entity], updates: List[tuple]):
        self.entity_type = entity_type
        self.updates = updates  # List of (field, operation, value) tuples
