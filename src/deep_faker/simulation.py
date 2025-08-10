"""Core simulation engine and management classes."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Type, Union

from faker import Faker

from .actions import AddDecay, Context, NewEvent, Select, SetState
from .base import BaseEvent, Entity, generate_fake_data


class FlowDefinition:
    """Container for flow function and its configuration."""

    def __init__(
        self,
        func: Callable,
        initiation_weight: float,
        filter_condition: Optional[Select] = None,
    ):
        self.func = func
        self.initiation_weight = initiation_weight
        self.filter_condition = filter_condition


class EntityManager:
    """Manages entity instances and their state."""

    def __init__(self):
        self.entities: Dict[Type[Entity], Dict[Any, Entity]] = {}

    def add_entity(self, entity_type: Type[Entity], entity: Entity):
        """Add an entity to the manager."""
        if entity_type not in self.entities:
            self.entities[entity_type] = {}

        primary_key = entity.get_primary_key()
        self.entities[entity_type][primary_key] = entity

    def get_entity(
        self, entity_type: Type[Entity], primary_key: Any
    ) -> Optional[Entity]:
        """Get an entity by type and primary key."""
        return self.entities.get(entity_type, {}).get(primary_key)

    def get_entities(self, entity_type: Type[Entity]) -> List[Entity]:
        """Get all entities of a given type."""
        return list(self.entities.get(entity_type, {}).values())

    def select_entities(self, selector: Select) -> List[Entity]:
        """Select entities based on filter conditions."""
        entities = self.get_entities(selector.entity_type)
        return [entity for entity in entities if selector.matches(entity)]

    def get_random_entity(self, entity_type: Type[Entity]) -> Optional[Entity]:
        """Get a random entity of the given type."""
        entities = self.get_entities(entity_type)
        return random.choice(entities) if entities else None


class Simulation:
    """Main simulation controller."""

    def __init__(
        self,
        duration: str = "1h",
        start_time: Union[str, datetime] = "now",
        random_seed: Optional[int] = None,
        initial_entities: Optional[Dict[Union[str, Type[Entity]], int]] = None,
    ):
        self.duration = self._parse_duration(duration)
        self.start_time = self._parse_start_time(start_time)
        self.random_seed = random_seed
        self.initial_entities = initial_entities or {}

        self.flows: List[FlowDefinition] = []
        self.outputs = []
        self.entity_manager = EntityManager()
        self.faker = Faker()
        self.current_time = self.start_time

        if random_seed is not None:
            random.seed(random_seed)
            self.faker.seed_instance(random_seed)

    def _parse_duration(self, duration: str) -> timedelta:
        """Parse duration string like '1h', '30m', '2d'."""
        if duration.endswith("s"):
            return timedelta(seconds=int(duration[:-1]))
        elif duration.endswith("m"):
            return timedelta(minutes=int(duration[:-1]))
        elif duration.endswith("h"):
            return timedelta(hours=int(duration[:-1]))
        elif duration.endswith("d"):
            return timedelta(days=int(duration[:-1]))
        else:
            return timedelta(hours=1)  # default

    def _parse_start_time(self, start_time: Union[str, datetime]) -> datetime:
        """Parse start time."""
        if isinstance(start_time, datetime):
            return start_time
        elif start_time == "now":
            return datetime.now()
        else:
            # Could parse other formats if needed
            return datetime.now()

    def flow(self, initiation_weight: float, filter: Optional[Select] = None):
        """Decorator to register a flow function."""

        def decorator(func: Callable):
            flow_def = FlowDefinition(func, initiation_weight, filter)
            self.flows.append(flow_def)
            return func

        return decorator

    def add_output(self, output):
        """Add an output handler."""
        self.outputs.append(output)

    def _initialize_entities(self):
        """Create initial entities based on configuration."""
        for entity_spec, count in self.initial_entities.items():
            if isinstance(entity_spec, str):
                # Find entity type by name
                entity_type = self._find_entity_type_by_name(entity_spec)
            else:
                entity_type = entity_spec

            if entity_type and entity_type.source_event:
                for _ in range(count):
                    # Generate fake event data and create entity
                    event_data = self._generate_event_data(entity_type.source_event)
                    entity = entity_type(**event_data)
                    self.entity_manager.add_entity(entity_type, entity)

    def _find_entity_type_by_name(self, name: str) -> Optional[Type[Entity]]:
        """Find entity type by class name."""
        # This would need to be improved for production use
        # For now, we'll return None and handle in the implementation
        return None

    def _generate_event_data(self, event_schema: Type[BaseEvent]) -> Dict[str, Any]:
        """Generate fake data for an event schema."""
        data = {}

        # Get field annotations
        for field_name, field_info in event_schema.model_fields.items():
            fake_value = generate_fake_data(field_info, self.faker)
            if fake_value is not None:
                data[field_name] = fake_value

        return data

    def _select_flow(self) -> Optional[FlowDefinition]:
        """Select a flow to run based on weights and filters."""
        eligible_flows = []

        for flow_def in self.flows:
            # Check filter condition
            if flow_def.filter_condition:
                matching_entities = self.entity_manager.select_entities(
                    flow_def.filter_condition
                )
                if not matching_entities:
                    continue

            eligible_flows.append(flow_def)

        if not eligible_flows:
            return None

        # Weight-based selection
        weights = [flow.initiation_weight for flow in eligible_flows]
        return random.choices(eligible_flows, weights=weights)[0]

    def _create_context(self, flow_def: FlowDefinition) -> Context:
        """Create context for flow execution."""
        selected_entity = None

        if flow_def.filter_condition:
            matching_entities = self.entity_manager.select_entities(
                flow_def.filter_condition
            )
            if matching_entities:
                selected_entity = random.choice(matching_entities)

        ctx = Context(self, self.current_time, selected_entity)
        return ctx

    def _process_action(self, action, ctx: Context):
        """Process a single action from a flow."""
        if isinstance(action, NewEvent):
            self._process_new_event(action, ctx)
        elif isinstance(action, AddDecay):
            return self._process_add_decay(action, ctx)
        elif isinstance(action, SetState):
            self._process_set_state(action, ctx)

        return False  # Continue flow

    def _process_new_event(self, action: NewEvent, ctx: Context):
        """Process NewEvent action."""
        # Generate event data
        event_data = self._generate_event_data(action.event_schema)

        # Use the created entity from context if available and no selected entity
        current_entity = ctx.selected_entity or ctx.created_entity

        # If we have an entity, use its primary key for matching field names
        if current_entity:
            pk_field = current_entity.primary_key
            pk_value = current_entity.get_primary_key()
            # Set the primary key value if the event has that field
            if pk_field in action.event_schema.model_fields:
                event_data[pk_field] = pk_value

        # Apply field overrides
        event_data.update(action.field_overrides)

        # Create event instance
        event = action.event_schema(**event_data)

        # Save entity if specified
        if action.save_entity:
            entity = action.save_entity(**event_data)
            self.entity_manager.add_entity(action.save_entity, entity)
            # Track the created entity in context for subsequent actions
            ctx.created_entity = entity
            current_entity = entity

        # Apply mutations
        if action.mutate and current_entity:
            current_entity.update_state(action.mutate.updates)

        # Send to outputs
        for output in self.outputs:
            output.send_event(event)

    def _process_add_decay(self, action: AddDecay, ctx: Context) -> bool:
        """Process AddDecay action. Returns True if flow should terminate."""
        # Advance time
        self.current_time += action.time_delta

        # Check for termination
        return random.random() < action.rate

    def _process_set_state(self, action: SetState, ctx: Context):
        """Process SetState action."""
        if ctx.selected_entity and isinstance(ctx.selected_entity, action.entity_type):
            ctx.selected_entity.update_state(action.updates)

    def run(self):
        """Run the simulation."""
        print(f"Starting simulation for {self.duration}")

        # Initialize entities
        self._initialize_entities()

        end_time = self.start_time + self.duration

        while self.current_time < end_time:
            # Select and run a flow
            flow_def = self._select_flow()
            if not flow_def:
                # No eligible flows, advance time and continue
                self.current_time += timedelta(seconds=1)
                continue

            # Create context and run flow
            ctx = self._create_context(flow_def)
            flow_generator = flow_def.func(ctx)

            try:
                # Execute flow actions
                for action in flow_generator:
                    should_terminate = self._process_action(action, ctx)
                    if should_terminate:
                        break

            except StopIteration:
                pass

        print(f"Simulation completed at {self.current_time}")

        # Clean up outputs
        for output in self.outputs:
            if hasattr(output, "close"):
                output.close()
