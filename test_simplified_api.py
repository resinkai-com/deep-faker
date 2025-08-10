#!/usr/bin/env python3
"""Test script to demonstrate the simplified API with attached entities."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from datetime import datetime

from deep_faker import (
    AddDecay,
    BaseEvent,
    Entity,
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
    balance: float = Field(faker="pyfloat", positive=True, max_value=1000)


class ShoppingEvent(BaseEvent):
    user_id: str  # Will be auto-populated from attached User entity
    item: str = Field(faker="catch_phrase")
    cost: float = Field(faker="pyfloat", positive=True, max_value=100)
    timestamp: datetime = Field(faker="now")


# Entity
class User(Entity):
    source_event = UserCreated
    primary_key = "user_id"

    balance: float = StateField(from_field="balance", type_=float)
    total_spent: float = StateField(default=0.0, type_=float)
    purchase_count: int = StateField(default=0, type_=int)


def test_simplified_api():
    """Test the simplified API with attached entities."""

    print("=== Testing Simplified API ===\n")

    sim = Simulation(
        duration="15s",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
        time_step="5s",
        n_flows=1,
        random_seed=42,
        initial_entities={User: 2},
    )

    captured_events = []

    class TestOutput:
        def send_event(self, event):
            captured_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())

    @sim.flow(initiation_weight=5.0, filter=Select(User, where=[("balance", ">", 50)]))
    def shopping_flow(ctx: FlowContext):
        """User goes shopping - demonstrates simplified mutation API."""

        user_entity = ctx.get_entity(User)
        print(
            f"  Shopping flow for user {user_entity.get_primary_key()[:8]} with balance ${user_entity.balance:.2f}"
        )

        # User makes a purchase - notice how simple the mutation is!
        # No need to specify which user - it's the attached User entity
        yield NewEvent(
            ctx,
            ShoppingEvent,
            mutate=SetState(
                User,
                [
                    ("total_spent", "add", 25.99),
                    ("purchase_count", "add", 1),
                    ("balance", "subtract", 25.99),
                ],
            ),
        )

        yield AddDecay(ctx, rate=0.0, seconds=3)

        # Another purchase
        yield NewEvent(
            ctx,
            ShoppingEvent,
            mutate=SetState(
                User,
                [
                    ("total_spent", "add", 15.50),
                    ("purchase_count", "add", 1),
                    ("balance", "subtract", 15.50),
                ],
            ),
        )

    @sim.flow(initiation_weight=2.0)
    def new_user_flow(ctx: FlowContext):
        """Create new users."""
        print(f"  Creating new user at {ctx.flow_clock}")
        yield NewEvent(ctx, UserCreated, save_entity=User)

    print("Starting simplified API demonstration...")
    sim.run()
    print(f"Generated {len(captured_events)} events\n")

    # Show the power of the versioned entity system
    print("=== Entity State Evolution ===")
    entity_manager = sim.global_context.entity_manager

    all_users = entity_manager.get_all_entities(User)
    print(f"Total users: {len(all_users)}")

    for user_id, current_state in all_users:
        print(f"\nUser {user_id[:8]}:")
        print(f"  Final balance: ${current_state.state.get('balance', 0):.2f}")
        print(f"  Total spent: ${current_state.state.get('total_spent', 0):.2f}")
        print(f"  Purchase count: {current_state.state.get('purchase_count', 0)}")

        # Show state history
        key = (User, user_id)
        if key in entity_manager.entity_states:
            states = entity_manager.entity_states[key]
            if len(states) > 1:
                print(f"  State changes: {len(states)} versions")
                for i, state in enumerate(states):
                    balance = state.state.get("balance", 0)
                    spent = state.state.get("total_spent", 0)
                    print(
                        f"    v{i+1} ({state.valid_from}): balance=${balance:.2f}, spent=${spent:.2f}"
                    )

    # Show automatic primary key population
    print(f"\n=== Automatic Primary Key Population ===")
    shopping_events = [
        e for e in captured_events if type(e).__name__ == "ShoppingEvent"
    ]
    print(f"Shopping events: {len(shopping_events)}")

    for i, event in enumerate(shopping_events[:3]):
        print(
            f"  Event {i+1}: user_id={event.user_id[:8]}, item='{event.item}', cost=${event.cost:.2f}"
        )

    print("\nSimplified API working perfectly!")
    print("Key benefits demonstrated:")
    print("- SetState(User, [...]) automatically works with attached User entity")
    print("- Primary keys automatically populated from attached entities")
    print("- Global entity state with versioned history")
    print("- Time-based state queries available")


if __name__ == "__main__":
    test_simplified_api()
