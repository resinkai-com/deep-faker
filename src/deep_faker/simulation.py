"""Core simulation engine and management classes."""

import random
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Type, Union

from faker import Faker

from .actions import (
    AddDecay,
    FlowContext,
    GlobalContext,
    NewEvent,
    Select,
    SetState,
)
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


class Simulation:
    """Main simulation controller."""

    def __init__(
        self,
        duration: str = "1h",
        start_time: Union[str, datetime] = "now",
        time_step: str = "1s",
        n_flows: int = 1,
        random_seed: Optional[int] = None,
        initial_entities: Optional[Dict[Union[str, Type[Entity]], int]] = None,
    ):
        self.duration = self._parse_duration(duration)
        self.start_time = self._parse_start_time(start_time)
        self.time_step = self._parse_duration(time_step)
        self.n_flows = n_flows
        self.random_seed = random_seed
        self.initial_entities = initial_entities or {}

        self.flows: List[FlowDefinition] = []
        self.outputs = []
        self.global_context = GlobalContext(self.start_time)
        self.faker = Faker()

        if random_seed is not None:
            random.seed(random_seed)
            self.faker.seed_instance(random_seed)

    @property
    def entity_manager(self):
        """Backward compatibility property for global_context."""
        return self.global_context

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
                    self.global_context.add_entity(entity_type, entity)

    def _find_entity_type_by_name(self, name: str) -> Optional[Type[Entity]]:
        """Find entity type by class name."""
        # This would need to be improved for production use
        # For now, we'll return None and handle in the implementation
        return None

    def _generate_event_data(
        self, event_schema: Type[BaseEvent], current_time: datetime = None
    ) -> Dict[str, Any]:
        """Generate fake data for an event schema."""
        data = {}

        # Use global context time if no specific time provided
        if current_time is None:
            current_time = self.global_context.global_clock

        # Get field annotations
        for field_name, field_info in event_schema.model_fields.items():
            fake_value = generate_fake_data(field_info, self.faker, current_time)
            if fake_value is not None:
                data[field_name] = fake_value

        return data

    def _select_flow(self) -> Optional[FlowDefinition]:
        """Select a flow to run based on weights and filters."""
        eligible_flows = []

        for flow_def in self.flows:
            # Check filter condition
            if flow_def.filter_condition:
                matching_entities = self.global_context.select_entities(
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

    def _create_flow_context(
        self, flow_def: FlowDefinition, flow_start_time: datetime
    ) -> FlowContext:
        """Create flow context for flow execution."""
        flow_name = getattr(flow_def.func, "__name__", "unknown_flow")
        flow_ctx = self.global_context.start_flow(flow_start_time, flow_name)

        # Select and assign entity if filter condition exists
        if flow_def.filter_condition:
            matching_entities = self.global_context.select_entities(
                flow_def.filter_condition
            )
            if matching_entities:
                selected_entity = random.choice(matching_entities)
                flow_ctx.add_entity(type(selected_entity), selected_entity)

        return flow_ctx

    def _process_action(self, action, flow_ctx: FlowContext):
        """Process a single action from a flow."""
        if isinstance(action, NewEvent):
            self._process_new_event(action, flow_ctx)
        elif isinstance(action, AddDecay):
            return self._process_add_decay(action, flow_ctx)
        elif isinstance(action, SetState):
            self._process_set_state(action, flow_ctx)

        return False  # Continue flow

    def _process_new_event(self, action: NewEvent, flow_ctx: FlowContext):
        """Process NewEvent action."""
        # Generate event data using flow's current time
        event_data = self._generate_event_data(action.event_schema, flow_ctx.flow_clock)

        # Populate primary key fields from entities in context
        self._populate_primary_keys_from_context(
            event_data, action.event_schema, flow_ctx
        )

        # Apply field overrides
        event_data.update(action.field_overrides)

        # Populate standard event metadata fields
        self._populate_event_metadata(event_data, flow_ctx)

        # Create event instance
        event = action.event_schema(**event_data)

        # Save entity if specified
        if action.save_entity:
            entity = action.save_entity(
                **event_data
            )  # action.save_entity = User, Product etc.
            self.global_context.add_entity(action.save_entity, entity)
            # Track the created entity in context for subsequent actions
            flow_ctx.add_entity(action.save_entity, entity)

        # Apply mutations
        if action.mutate:
            # Mutate the attached entity's state
            try:
                flow_ctx.mutate_selected_entity(
                    action.mutate.entity_type, action.mutate.updates
                )
            except ValueError:
                # Entity not attached - this is OK, mutation is ignored
                pass

        # Send to outputs
        for output in self.outputs:
            output.send_event(event)

    def _populate_primary_keys_from_context(
        self,
        event_data: Dict[str, Any],
        event_schema: Type[BaseEvent],
        flow_ctx: FlowContext,
    ):
        """Populate primary key fields in event data from entities in context."""
        # Check each field in the event schema
        for field_name in event_schema.model_fields.keys():
            # Skip if field already has data
            if field_name in event_data and event_data[field_name] is not None:
                continue

            # Look for a selected entity that has this field as its primary key
            for entity_type, entity_id in flow_ctx.selected_entities.items():
                if entity_type.primary_key == field_name:
                    event_data[field_name] = entity_id
                    break

    def _populate_event_metadata(
        self, event_data: Dict[str, Any], flow_ctx: FlowContext
    ):
        """Populate standard event metadata fields."""
        import uuid

        try:
            import shortuuid
        except ImportError:
            shortuuid = None

        # Generate unique event ID
        if shortuuid:
            event_data["sys__eid"] = shortuuid.uuid()[:12]  # 12 character short UUID
        else:
            event_data["sys__eid"] = str(uuid.uuid4()).replace("-", "")[:12]  # Fallback

        # Set event timestamp in milliseconds using flow clock
        timestamp_ms = int(flow_ctx.flow_clock.timestamp() * 1000)
        event_data["sys__ets"] = timestamp_ms

        # Set session ID from context
        event_data["sys__sid"] = flow_ctx.session_id

    def _process_add_decay(self, action: AddDecay, flow_ctx: FlowContext) -> bool:
        """Process AddDecay action. Returns True if flow should terminate."""
        # Advance flow time
        flow_ctx.advance_time(action.time_delta)

        # Check for termination
        return random.random() < action.rate

    def _process_set_state(self, action: SetState, flow_ctx: FlowContext):
        """Process SetState action."""
        try:
            flow_ctx.mutate_selected_entity(action.entity_type, action.updates)
        except ValueError:
            # Entity not attached - this is OK, mutation is ignored
            pass

    def run(self):
        """Run the simulation using the new time-step based approach."""
        print(
            f"Starting simulation for {self.duration} with time_step={self.time_step} and n_flows={self.n_flows}"
        )

        # Initialize entities
        self._initialize_entities()

        end_time = self.start_time + self.duration
        ti = self.start_time

        while ti < end_time:
            tj = ti + self.time_step
            if tj > end_time:
                tj = end_time

            # Update global context time
            self.global_context.global_clock = ti

            # Launch n_flows concurrent flows in this time step
            active_flows = []

            for _ in range(self.n_flows):
                # Select a flow
                flow_def = self._select_flow()
                if not flow_def:
                    continue

                # Random start time within [ti, tj)
                if ti == tj:
                    tf = ti
                else:
                    delta_seconds = (tj - ti).total_seconds()
                    random_offset = random.random() * delta_seconds
                    tf = ti + timedelta(seconds=random_offset)

                # Create flow context
                flow_ctx = self._create_flow_context(flow_def, tf)

                # Start flow execution
                flow_info = {
                    "flow_def": flow_def,
                    "flow_ctx": flow_ctx,
                    "generator": flow_def.func(flow_ctx),
                    "active": True,
                }
                active_flows.append(flow_info)

            # Execute all active flows until completion or time step end
            while active_flows:
                completed_flows = []

                for i, flow_info in enumerate(active_flows):
                    if not flow_info["active"]:
                        completed_flows.append(i)
                        continue

                    try:
                        # Get next action from flow
                        action = next(flow_info["generator"])

                        # Process the action
                        should_terminate = self._process_action(
                            action, flow_info["flow_ctx"]
                        )
                        if should_terminate:
                            flow_info["active"] = False
                            completed_flows.append(i)

                        # If flow time exceeds time step, pause it (this is simplified)
                        if flow_info["flow_ctx"].flow_clock > tj:
                            # In a more complex implementation, we might reschedule
                            flow_info["active"] = False
                            completed_flows.append(i)

                    except StopIteration:
                        # Flow completed naturally
                        flow_info["active"] = False
                        completed_flows.append(i)

                # Remove completed flows (in reverse order to maintain indices)
                for i in reversed(completed_flows):
                    if i < len(active_flows):  # Safety check
                        flow = active_flows[i]
                        flow["flow_ctx"].cleanup()  # Release entities
                        active_flows.pop(i)

            # Advance to next time step
            ti = tj

        print(f"Simulation completed at {ti}")

        # Clean up outputs
        for output in self.outputs:
            if hasattr(output, "close"):
                output.close()
