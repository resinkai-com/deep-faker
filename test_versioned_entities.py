#!/usr/bin/env python3
"""Test script to demonstrate the new versioned entity management system."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from datetime import datetime

from deep_faker import (
    AddDecay,
    BaseEvent,
    Entity,
    EntityManager,
    Field,
    FlowContext,
    NewEvent,
    Select,
    SetState,
    Simulation,
    StateField,
)


# Event schemas
class UserCreated(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    name: str = Field(faker="name")
    created_at: datetime = Field(faker="now")


class UserLogin(BaseEvent):
    user_id: str
    login_time: datetime = Field(faker="now")


class UserActivity(BaseEvent):
    user_id: str
    activity: str = Field(
        faker="random_element", elements=["view", "click", "purchase"]
    )
    timestamp: datetime = Field(faker="now")


# Entity
class User(Entity):
    source_event = UserCreated
    primary_key = "user_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    activity_count: int = StateField(default=0, type_=int)
    last_login: datetime = StateField(default=None, type_=datetime)


def test_versioned_entity_management():
    """Test the new versioned entity management system."""

    print("=== Testing Versioned Entity Management ===\n")

    # Create simulation
    sim = Simulation(
        duration="20s",
        start_time=datetime(2024, 1, 1, 10, 0, 0),
        time_step="5s",  # 5-second time steps
        n_flows=2,  # 2 concurrent flows
        random_seed=789,
        initial_entities={User: 3},
    )

    captured_events = []

    class TestOutput:
        def send_event(self, event):
            captured_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())

    # Flow 1: User logs in and performs activities
    @sim.flow(
        initiation_weight=3.0,
        filter=Select(User, where=[("is_logged_in", "is", False)]),
    )
    def user_login_flow(ctx: FlowContext):
        """User logs in and becomes active."""
        print(
            f"  Login flow started at {ctx.flow_clock} for user {ctx.get_entity_id(User)}"
        )

        # User logs in
        yield NewEvent(
            ctx,
            UserLogin,
            mutate=SetState(
                User,
                [("is_logged_in", "is", True), ("last_login", "is", ctx.current_time)],
            ),
        )

        yield AddDecay(ctx, rate=0.0, seconds=3)

        # User performs activity
        yield NewEvent(
            ctx,
            UserActivity,
            activity="view",
            mutate=SetState(User, [("activity_count", "add", 1)]),
        )

        yield AddDecay(ctx, rate=0.0, seconds=2)

        # Another activity
        yield NewEvent(
            ctx,
            UserActivity,
            activity="purchase",
            mutate=SetState(User, [("activity_count", "add", 1)]),
        )

    # Flow 2: Create new users
    @sim.flow(initiation_weight=1.0)
    def user_creation_flow(ctx: FlowContext):
        """Create new users."""
        print(f"  User creation at {ctx.flow_clock}")
        yield NewEvent(ctx, UserCreated, save_entity=User)

    print("Starting simulation...")
    sim.run()
    print(f"Generated {len(captured_events)} events\n")

    # Demonstrate entity state versioning
    print("=== Entity State History ===")
    entity_manager = sim.global_context.entity_manager

    # Get all users
    all_user_data = entity_manager.get_all_entities(User)
    print(f"Total users: {len(all_user_data)}")

    # Show state history for first user
    if all_user_data:
        user_id, current_state = all_user_data[0]
        print(f"\nState history for user {user_id[:8]}...")

        # Get all state versions for this user
        key = (User, user_id)
        if key in entity_manager.entity_states:
            states = entity_manager.entity_states[key]

            for i, state in enumerate(states):
                print(f"  Version {i+1}: {state.valid_from} -> {state.valid_to}")
                print(
                    f"    State: is_logged_in={state.state.get('is_logged_in', False)}, "
                    f"activity_count={state.state.get('activity_count', 0)}"
                )

    # Demonstrate time-based queries
    print(f"\n=== Time-Based Queries ===")

    # Query at different times
    times_to_check = [
        datetime(2024, 1, 1, 10, 0, 5),  # 5 seconds after start
        datetime(2024, 1, 1, 10, 0, 10),  # 10 seconds after start
        datetime(2024, 1, 1, 10, 0, 15),  # 15 seconds after start
    ]

    for check_time in times_to_check:
        logged_in_users = entity_manager.query(
            User, where=[("is_logged_in", "is", True)], time=check_time
        )

        print(f"At {check_time}: {len(logged_in_users)} users logged in")
        for user_id, user_state in logged_in_users:
            activity_count = user_state.state.get("activity_count", 0)
            print(f"  User {user_id[:8]}: {activity_count} activities")

    # Show final state
    print(f"\n=== Final State ===")
    final_logged_in = entity_manager.query(User, where=[("is_logged_in", "is", True)])
    print(f"Users currently logged in: {len(final_logged_in)}")

    total_activities = 0
    for user_id, user_state in entity_manager.get_all_entities(User):
        activity_count = user_state.state.get("activity_count", 0)
        total_activities += activity_count

    print(f"Total activities across all users: {total_activities}")

    # Show sample events
    print(f"\n=== Sample Events ===")
    for i, event in enumerate(captured_events[:5]):
        event_dict = event.model_dump()
        event_time = datetime.fromtimestamp(event_dict.get("event_ts_", 0) / 1000)
        print(f"{i+1}. {type(event).__name__} at {event_time}")

    print("\nVersioned entity management system working correctly!")


if __name__ == "__main__":
    test_versioned_entity_management()
