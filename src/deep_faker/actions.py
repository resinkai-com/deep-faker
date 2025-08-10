"""Action classes for declarative flow definitions."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Type, Union

from .base import BaseEvent, Entity
from .entity_manager import EntityManager


class GlobalContext:
    """Global simulation context managing available entities and global clock."""

    def __init__(self, start_time: datetime):
        self.global_clock = start_time
        self.entity_manager = EntityManager()

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity with its initial state."""
        self.entity_manager.add_entity(entity_type, entity, self.global_clock)

    def get_available_entities(self, entity_type: Type[Entity]) -> List[Entity]:
        """Get all available (non-active) entities of a given type."""
        available_data = self.entity_manager.get_available_entities(
            entity_type, time=self.global_clock
        )
        entities = []
        for entity_id, entity_state in available_data:
            entity = self.entity_manager.create_entity_instance(
                entity_type, entity_id, self.global_clock
            )
            if entity:
                entities.append(entity)
        return entities

    def select_entities(self, selector: "Select") -> List[Entity]:
        """Select available entities based on filter conditions."""
        available_data = self.entity_manager.get_available_entities(
            entity_type=selector.entity_type,
            where=selector.where,
            time=self.global_clock,
        )
        entities = []
        for entity_id, entity_state in available_data:
            entity = self.entity_manager.create_entity_instance(
                selector.entity_type, entity_id, self.global_clock
            )
            if entity:
                entities.append(entity)
        return entities

    def set_entity_flow(
        self, entity_type: Type[Entity], entity: Entity, flow_name: Optional[str]
    ):
        """Set the flow_name for an entity (implicit state mutation)."""
        entity_id = entity.get_primary_key()
        self.entity_manager.set_entity_flow(
            entity_type, entity_id, flow_name, self.global_clock
        )

    def get_random_available_entity(
        self, entity_type: Type[Entity]
    ) -> Optional[Entity]:
        """Get a random available entity of the given type."""
        available = self.get_available_entities(entity_type)
        return random.choice(available) if available else None

    def get_entities(self, entity_type: Type[Entity]) -> List[Entity]:
        """Backward compatibility method - returns all entities including active ones."""
        all_data = self.entity_manager.get_all_entities(entity_type, self.global_clock)
        entities = []
        for entity_id, entity_state in all_data:
            entity = self.entity_manager.create_entity_instance(
                entity_type, entity_id, self.global_clock
            )
            if entity:
                entities.append(entity)
        return entities

    def start_flow(
        self, flow_start_time: datetime, flow_name: str = None
    ) -> "FlowContext":
        """Start a new flow and return its context."""
        try:
            import shortuuid

            session_id = shortuuid.uuid()[:8]  # 8 character session ID
        except ImportError:
            session_id = str(uuid.uuid4()).replace("-", "")[:8]  # Fallback
        if flow_name is None:
            flow_name = f"flow_{session_id}"
        return FlowContext(self, session_id, flow_start_time, flow_name)


class FlowContext:
    """Flow-specific context maintaining session state and flow clock."""

    def __init__(
        self,
        global_context: GlobalContext,
        session_id: str,
        start_time: datetime,
        flow_name: str,
    ):
        self.global_context = global_context
        self.session_id = session_id
        self.flow_clock = start_time
        self.flow_name = flow_name
        # Store selected entities by (entity_type, entity_id)
        self.selected_entities: Dict[Type[Entity], str] = {}

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity to this flow context."""
        entity_id = entity.get_primary_key()
        self.selected_entities[entity_type] = entity_id
        # Set entity flow_name (implicit mutation)
        self.global_context.set_entity_flow(entity_type, entity, self.flow_name)

    def get_entity(self, entity_type: Type[Entity]) -> Optional[Entity]:
        """Get a selected entity of the specified type from the flow context."""
        if entity_type not in self.selected_entities:
            return None

        entity_id = self.selected_entities[entity_type]
        return self.global_context.entity_manager.create_entity_instance(
            entity_type, entity_id, self.flow_clock
        )

    def get_entity_id(self, entity_type: Type[Entity]) -> Optional[str]:
        """Get the ID of a selected entity."""
        return self.selected_entities.get(entity_type)

    def advance_time(self, delta: timedelta):
        """Advance the flow clock."""
        self.flow_clock += delta

    def get_primary_entity(self) -> Optional[Entity]:
        """Get the primary entity (first selected entity)."""
        if self.selected_entities:
            # Return the first selected entity
            entity_type = next(iter(self.selected_entities.keys()))
            return self.get_entity(entity_type)
        return None

    def mutate_selected_entity(self, entity_type: Type[Entity], updates: List[Tuple]):
        """Mutate the state of a selected entity."""
        if entity_type not in self.selected_entities:
            raise ValueError(f"No {entity_type.__name__} entity selected for this flow")

        entity_id = self.selected_entities[entity_type]
        self.global_context.entity_manager.mutate_state(
            entity_type, entity_id, updates, self.flow_clock
        )

    @property
    def current_time(self) -> datetime:
        """Backward compatibility property for flow_clock."""
        return self.flow_clock

    @property
    def entities_by_type(self) -> Dict[Type[Entity], Entity]:
        """Backward compatibility property - creates entity instances on demand."""
        entities = {}
        for entity_type, entity_id in self.selected_entities.items():
            entity = self.global_context.entity_manager.create_entity_instance(
                entity_type, entity_id, self.flow_clock
            )
            if entity:
                entities[entity_type] = entity
        return entities

    def cleanup(self):
        """Mark all entities used by this flow as available again (remove flow_name)."""
        for entity_type, entity_id in self.selected_entities.items():
            self.global_context.entity_manager.set_entity_flow(
                entity_type, entity_id, None, self.flow_clock
            )


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
        if session_id:
            self.session_id = session_id
        else:
            try:
                import shortuuid

                self.session_id = shortuuid.uuid()[:8]  # 8 character session ID
            except ImportError:
                self.session_id = str(uuid.uuid4()).replace("-", "")[:8]  # Fallback

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
