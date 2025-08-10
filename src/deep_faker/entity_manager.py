"""Entity management with versioned state tracking."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

from .base import Entity


class EntityState:
    """Represents a versioned state for an entity."""

    def __init__(
        self,
        entity_type: Type[Entity],
        entity_id: str,
        state: Dict[str, Any],
        valid_from: datetime,
        valid_to: Optional[datetime] = None,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.state = state.copy()  # Deep copy to avoid mutations
        self.valid_from = valid_from
        self.valid_to = valid_to

    def is_valid_at(self, time: datetime) -> bool:
        """Check if this state is valid at the given time."""
        if time < self.valid_from:
            return False
        if self.valid_to is not None and time >= self.valid_to:
            return False
        return True

    def __repr__(self):
        return f"EntityState({self.entity_type.__name__}, id:{self.entity_id}, valid_from:{self.valid_from}, valid_to:{self.valid_to})"


class EntityManager:
    """Manages entities with versioned state tracking across simulation time."""

    def __init__(self):
        # Track all entity states by (entity_type, entity_id)
        self.entity_states: Dict[Tuple[Type[Entity], str], List[EntityState]] = {}

    def add_entity(
        self, entity_type: Type[Entity], entity: Entity, time: datetime
    ) -> None:
        """Add a new entity with its initial state."""
        entity_id = entity.get_primary_key()
        key = (entity_type, entity_id)

        # Extract state from entity
        state = {}
        for field_name, field in entity_type._state_fields.items():
            state[field_name] = getattr(entity, field_name)

        # Add any other attributes that might be set
        for attr_name, attr_value in entity.__dict__.items():
            if not attr_name.startswith("_") and attr_name not in state:
                state[attr_name] = attr_value

        # Add implicit flow_name state field (None = available)
        state["flow_name"] = None

        # Create initial state version
        entity_state = EntityState(entity_type, entity_id, state, time)

        if key not in self.entity_states:
            self.entity_states[key] = []

        self.entity_states[key].append(entity_state)

    def get_entity_state(
        self, entity_type: Type[Entity], entity_id: str, time: Optional[datetime] = None
    ) -> Optional[EntityState]:
        """Get the entity state valid at the specified time."""
        key = (entity_type, entity_id)

        if key not in self.entity_states:
            return None

        if time is None:
            # Return the most recent state (with valid_to = None)
            for state in reversed(self.entity_states[key]):
                if state.valid_to is None:
                    return state
            # If no current state, return the last one
            return self.entity_states[key][-1] if self.entity_states[key] else None

        # Find state valid at the given time
        for state in self.entity_states[key]:
            if state.is_valid_at(time):
                return state

        return None

    def query(
        self,
        entity_type: Type[Entity],
        where: Optional[List[Tuple]] = None,
        time: Optional[datetime] = None,
    ) -> List[Tuple[str, EntityState]]:
        """Query entities based on conditions at a specific time.

        Returns list of (entity_id, entity_state) tuples.
        """
        results = []

        # Get all entities of this type
        for (etype, entity_id), states in self.entity_states.items():
            if etype != entity_type:
                continue

            # Get state at the specified time
            entity_state = self.get_entity_state(entity_type, entity_id, time)
            if entity_state is None:
                continue

            # Apply where conditions
            if where:
                matches = True
                for field, operation, value in where:
                    entity_value = entity_state.state.get(field)

                    if operation == "is" or operation == "=":
                        if entity_value != value:
                            matches = False
                            break
                    elif operation == "is_not" or operation == "!=":
                        if entity_value == value:
                            matches = False
                            break
                    elif operation == "greater_than" or operation == ">":
                        if not (entity_value is not None and entity_value > value):
                            matches = False
                            break
                    elif operation == "less_than" or operation == "<":
                        if not (entity_value is not None and entity_value < value):
                            matches = False
                            break
                    elif operation == "in":
                        if entity_value not in value:
                            matches = False
                            break

                if not matches:
                    continue

            results.append((entity_id, entity_state))

        return results

    def get_available_entities(
        self,
        entity_type: Type[Entity],
        where: Optional[List[Tuple]] = None,
        time: Optional[datetime] = None,
    ) -> List[Tuple[str, EntityState]]:
        """Get available entities (flow_name is None) matching the criteria."""
        # Add implicit filter for available entities
        implicit_filter = [("flow_name", "is", None)]

        # Combine with custom where conditions
        combined_where = implicit_filter[:]
        if where:
            combined_where.extend(where)

        return self.query(entity_type, combined_where, time)

    def insert_state(
        self,
        entity_type: Type[Entity],
        entity_id: str,
        state_updates: List[Tuple],
        time: datetime,
    ) -> None:
        """Insert a new state version for an entity."""
        key = (entity_type, entity_id)

        if key not in self.entity_states:
            raise ValueError(
                f"Entity {entity_type.__name__} with id {entity_id} does not exist"
            )

        # Get the current state
        current_state = self.get_entity_state(entity_type, entity_id)
        if current_state is None:
            raise ValueError(
                f"No current state found for entity {entity_type.__name__} with id {entity_id}"
            )

        # Close the current state
        if current_state.valid_to is None:
            current_state.valid_to = time

        # Create new state by copying current and applying updates
        new_state = current_state.state.copy()

        # Apply state updates with operations
        for field, operation, value in state_updates:
            if operation == "is" or operation == "=":
                new_state[field] = value
            elif operation == "add":
                current_value = new_state.get(field, 0)
                new_state[field] = current_value + value
            elif operation == "subtract":
                current_value = new_state.get(field, 0)
                new_state[field] = current_value - value
            else:
                # Default to assignment
                new_state[field] = value

        # Create new state version
        entity_state = EntityState(entity_type, entity_id, new_state, time)
        self.entity_states[key].append(entity_state)

    def mutate_state(
        self,
        entity_type: Type[Entity],
        entity_id: str,
        updates: List[Tuple],
        time: datetime,
    ) -> None:
        """Mutate entity state with a list of (field, operation, value) updates."""
        self.insert_state(entity_type, entity_id, updates, time)

    def set_entity_flow(
        self,
        entity_type: Type[Entity],
        entity_id: str,
        flow_name: Optional[str],
        time: datetime,
    ) -> None:
        """Set the flow_name for an entity (implicit state mutation)."""
        self.mutate_state(
            entity_type, entity_id, [("flow_name", "is", flow_name)], time
        )

    def is_entity_active(
        self, entity_type: Type[Entity], entity_id: str, time: Optional[datetime] = None
    ) -> bool:
        """Check if an entity is currently active (has a flow_name)."""
        entity_state = self.get_entity_state(entity_type, entity_id, time)
        if entity_state is None:
            return False
        return entity_state.state.get("flow_name") is not None

    def create_entity_instance(
        self, entity_type: Type[Entity], entity_id: str, time: Optional[datetime] = None
    ) -> Optional[Entity]:
        """Create an Entity instance from the stored state at the given time."""
        entity_state = self.get_entity_state(entity_type, entity_id, time)
        if entity_state is None:
            return None

        # Create entity instance with state
        entity = entity_type()
        entity._primary_key_value = entity_id

        # Set state fields
        for field_name, value in entity_state.state.items():
            if hasattr(entity, field_name):
                setattr(entity, field_name, value)
            else:
                # Store in _state for state fields
                if not hasattr(entity, "_state"):
                    entity._state = {}
                entity._state[field_name] = value

        return entity

    def get_all_entities(
        self, entity_type: Type[Entity], time: Optional[datetime] = None
    ) -> List[Tuple[str, EntityState]]:
        """Get all entities of a type, including active ones."""
        return self.query(entity_type, None, time)
