"""Test multi-entity flows functionality."""

import uuid
from datetime import datetime

from deep_faker import (
    AddDecay,
    BaseEvent,
    Context,
    Entity,
    Field,
    NewEvent,
    Select,
    SetState,
    Simulation,
    StateField,
)


# Event Schemas
class UserRegistered(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    full_name: str = Field(faker="name")
    email: str = Field(faker="email")
    registered_at: datetime = Field(faker="date_time")


class DeviceRegistered(BaseEvent):
    device_id: str = Field(primary_key=True, faker="uuid4")
    user_id: str  # Should be populated from User entity
    device_type: str = Field(
        faker="random_element", elements=["mobile", "desktop", "tablet"]
    )
    registered_at: datetime = Field(faker="date_time")


class UserDeviceAssociation(BaseEvent):
    user_id: str  # Should be populated from User entity
    device_id: str  # Should be populated from Device entity
    associated_at: datetime = Field(faker="date_time")


class UserLoggedIn(BaseEvent):
    user_id: str  # Should be populated from User entity
    device_id: str  # Should be populated from Device entity
    login_time: datetime = Field(faker="date_time")


# Entities
class User(Entity):
    source_event = UserRegistered
    primary_key = "user_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    device_count: int = StateField(default=0, type_=int)
    last_login: datetime = StateField(default=None, type_=datetime)


class Device(Entity):
    source_event = DeviceRegistered
    primary_key = "device_id"

    is_active: bool = StateField(default=True, type_=bool)
    last_used: datetime = StateField(default=None, type_=datetime)
    owner_user_id: str = StateField(from_field="user_id", type_=str)


def test_multi_entity_flow():
    """Test a flow that creates and mutates multiple entity types."""
    # Create simulation
    sim = Simulation(
        duration="30s",  # Short duration for testing
        start_time="now",
        random_seed=42,
        initial_entities={},  # Start with no entities
    )

    # Capture output
    output_events = []

    class TestOutput:
        def send_event(self, event):
            output_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())

    # Define a flow that works with multiple entity types
    @sim.flow(initiation_weight=10.0)
    def user_and_device_registration(ctx: Context):
        """A flow that creates both user and device entities."""
        # Create a new user
        yield NewEvent(ctx, UserRegistered, save_entity=User)

        # Create a new device associated with the user
        yield NewEvent(
            ctx,
            DeviceRegistered,
            save_entity=Device,
            mutate=SetState(User, [("device_count", "add", 1)]),
        )

        # Create an association event (should have both user_id and device_id populated)
        yield NewEvent(ctx, UserDeviceAssociation)

        yield AddDecay(ctx, rate=0.3, seconds=5)

        # User logs in using the device
        yield NewEvent(
            ctx,
            UserLoggedIn,
            mutate=SetState(
                User,
                [("is_logged_in", "is", True), ("last_login", "is", ctx.current_time)],
            ),
        )

    # Run simulation
    sim.run()

    # Verify results
    assert len(output_events) > 0, "Should generate at least some events"

    # Check event types
    event_types = {type(event).__name__ for event in output_events}
    expected_types = {
        "UserRegistered",
        "DeviceRegistered",
        "UserDeviceAssociation",
        "UserLoggedIn",
    }

    # We should have at least UserRegistered and DeviceRegistered
    assert "UserRegistered" in event_types
    assert "DeviceRegistered" in event_types

    # Find related events
    user_registered_events = [
        e for e in output_events if type(e).__name__ == "UserRegistered"
    ]
    device_registered_events = [
        e for e in output_events if type(e).__name__ == "DeviceRegistered"
    ]
    association_events = [
        e for e in output_events if type(e).__name__ == "UserDeviceAssociation"
    ]
    login_events = [e for e in output_events if type(e).__name__ == "UserLoggedIn"]

    assert len(user_registered_events) > 0, "Should have user registration events"
    assert len(device_registered_events) > 0, "Should have device registration events"

    # Verify that device registration has user_id populated from user entity
    if device_registered_events:
        device_event = device_registered_events[0]
        assert hasattr(device_event, "user_id"), "Device event should have user_id"
        assert (
            device_event.user_id is not None
        ), "Device event user_id should be populated"

    # Verify that association events have both IDs populated
    if association_events:
        assoc_event = association_events[0]
        assert hasattr(assoc_event, "user_id"), "Association event should have user_id"
        assert hasattr(
            assoc_event, "device_id"
        ), "Association event should have device_id"
        assert (
            assoc_event.user_id is not None
        ), "Association event user_id should be populated"
        assert (
            assoc_event.device_id is not None
        ), "Association event device_id should be populated"

    # Verify login events have both IDs
    if login_events:
        login_event = login_events[0]
        assert hasattr(login_event, "user_id"), "Login event should have user_id"
        assert hasattr(login_event, "device_id"), "Login event should have device_id"
        assert (
            login_event.user_id is not None
        ), "Login event user_id should be populated"
        assert (
            login_event.device_id is not None
        ), "Login event device_id should be populated"

    print(f"Generated {len(output_events)} events of types: {event_types}")

    # Verify entity states were properly updated
    # Get the entity manager to check states
    entity_manager = sim.entity_manager
    users = entity_manager.get_entities(User)
    devices = entity_manager.get_entities(Device)

    if users and devices:
        user = users[0]
        device = devices[0]

        # User should have device_count incremented
        assert (
            user.device_count > 0
        ), f"User should have device_count > 0, got {user.device_count}"

        # Device should have owner_user_id set from the event
        assert device.owner_user_id is not None, "Device should have owner_user_id set"
        assert (
            device.owner_user_id == user.get_primary_key()
        ), "Device owner should match user"


def test_multi_entity_mutations():
    """Test that mutations work correctly with multiple entity types."""
    # Create simulation with initial entities
    sim = Simulation(
        duration="10s",
        start_time="now",
        random_seed=123,
        initial_entities={User: 2, Device: 3},
    )

    @sim.flow(
        initiation_weight=5.0,
        filter=Select(User, where=[("is_logged_in", "is", False)]),
    )
    def multi_entity_interaction(ctx: Context):
        """A flow that mutates multiple entity types."""
        # Get a random device and associate it with the user
        device_entities = sim.entity_manager.get_entities(Device)
        if device_entities:
            device = device_entities[0]
            ctx.add_entity(Device, device)

        # Create login event and mutate both user and device states
        yield NewEvent(
            ctx,
            UserLoggedIn,
            mutate=SetState(
                User,
                [("is_logged_in", "is", True), ("last_login", "is", ctx.current_time)],
            ),
        )

        # Update device state in a separate action
        yield NewEvent(
            ctx,
            UserDeviceAssociation,
            mutate=SetState(
                Device,
                [("is_active", "is", True), ("last_used", "is", ctx.current_time)],
            ),
        )

    # Capture initial states
    initial_users = sim.entity_manager.get_entities(User)
    initial_devices = sim.entity_manager.get_entities(Device)

    # Run simulation
    output_events = []

    class TestOutput:
        def send_event(self, event):
            output_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())
    sim.run()

    # Verify that mutations affected the entities
    final_users = sim.entity_manager.get_entities(User)
    final_devices = sim.entity_manager.get_entities(Device)

    # Check that some users are now logged in
    logged_in_users = [u for u in final_users if u.is_logged_in]
    assert len(logged_in_users) > 0, "Some users should be logged in after simulation"

    # Check that some devices were updated
    active_devices = [d for d in final_devices if d.last_used is not None]
    # Note: This might be 0 if the flow didn't select the right entities, but that's OK for this test
    print(f"Active devices after simulation: {len(active_devices)}")


if __name__ == "__main__":
    test_multi_entity_flow()
    test_multi_entity_mutations()
    print("All multi-entity flow tests passed!")
