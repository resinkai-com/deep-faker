"""Action classes for declarative flow definitions."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Type, Union

from .base import BaseEvent, Entity


class GlobalContext:
    """Global simulation context managing available entities and global clock."""

    def __init__(self, start_time: datetime):
        self.global_clock = start_time
        self.available_entities: Dict[Type[Entity], Dict[str, Entity]] = {}
        self.active_entities: Dict[Type[Entity], Set[str]] = {}

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity to available entities."""
        if entity_type not in self.available_entities:
            self.available_entities[entity_type] = {}
        if entity_type not in self.active_entities:
            self.active_entities[entity_type] = set()

        pk = entity.get_primary_key()
        self.available_entities[entity_type][pk] = entity

    def get_available_entities(self, entity_type: Type[Entity]) -> List[Entity]:
        """Get all available (non-active) entities of a given type."""
        if entity_type not in self.available_entities:
            return []

        available = []
        active_keys = self.active_entities.get(entity_type, set())

        for pk, entity in self.available_entities[entity_type].items():
            if pk not in active_keys:
                available.append(entity)

        return available

    def select_entities(self, selector: "Select") -> List[Entity]:
        """Select available entities based on filter conditions."""
        available_entities = self.get_available_entities(selector.entity_type)
        return [entity for entity in available_entities if selector.matches(entity)]

    def mark_entity_active(self, entity_type: Type[Entity], entity: Entity):
        """Mark an entity as active (being used by a flow)."""
        if entity_type not in self.active_entities:
            self.active_entities[entity_type] = set()
        pk = entity.get_primary_key()
        self.active_entities[entity_type].add(pk)

    def mark_entity_available(self, entity_type: Type[Entity], entity: Entity):
        """Mark an entity as available (no longer being used by a flow)."""
        if entity_type in self.active_entities:
            pk = entity.get_primary_key()
            self.active_entities[entity_type].discard(pk)

    def get_random_available_entity(
        self, entity_type: Type[Entity]
    ) -> Optional[Entity]:
        """Get a random available entity of the given type."""
        available = self.get_available_entities(entity_type)
        return random.choice(available) if available else None

    def get_entities(self, entity_type: Type[Entity]) -> List[Entity]:
        """Backward compatibility method - returns all entities including active ones."""
        if entity_type not in self.available_entities:
            return []
        return list(self.available_entities[entity_type].values())

    def start_flow(self, flow_start_time: datetime) -> "FlowContext":
        """Start a new flow and return its context."""
        session_id = str(uuid.uuid4())
        return FlowContext(self, session_id, flow_start_time)


class FlowContext:
    """Flow-specific context maintaining session state and flow clock."""

    def __init__(
        self, global_context: GlobalContext, session_id: str, start_time: datetime
    ):
        self.global_context = global_context
        self.session_id = session_id
        self.flow_clock = start_time
        self.selected_entity: Optional[Entity] = None
        self.entities_by_type: Dict[Type[Entity], Entity] = {}
        self.active_entity_types: Set[Type[Entity]] = (
            set()
        )  # Track which entity types this flow is using

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity to this flow context."""
        self.entities_by_type[entity_type] = entity
        self.active_entity_types.add(entity_type)
        # Mark entity as active in global context
        self.global_context.mark_entity_active(entity_type, entity)

    def get_entity(self, entity_type: Type[Entity]) -> Optional[Entity]:
        """Get an entity of the specified type from the flow context."""
        return self.entities_by_type.get(entity_type)

    def advance_time(self, delta: timedelta):
        """Advance the flow clock."""
        self.flow_clock += delta

    def get_primary_entity(self) -> Optional[Entity]:
        """Get the primary entity (selected or first created)."""
        if self.selected_entity:
            return self.selected_entity
        if self.entities_by_type:
            return next(iter(self.entities_by_type.values()))
        return None

    @property
    def current_time(self) -> datetime:
        """Backward compatibility property for flow_clock."""
        return self.flow_clock

    def cleanup(self):
        """Mark all entities used by this flow as available again."""
        for entity_type in self.active_entity_types:
            if entity_type in self.entities_by_type:
                entity = self.entities_by_type[entity_type]
                self.global_context.mark_entity_available(entity_type, entity)


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
        ctx: Union["Context", "FlowContext"],
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

    def __init__(
        self, ctx: Union["Context", "FlowContext"], rate: float, **kwargs_for_time_delta
    ):
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
