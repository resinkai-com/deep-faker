"""End-to-end test for E-commerce event simulation."""

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
    registered_at: datetime = Field(faker="date_time_this_decade")


class UserLoggedIn(BaseEvent):
    user_id: str
    login_time: datetime = Field(faker="date_time")


class ProductCreated(BaseEvent):
    product_id: str = Field(primary_key=True, faker="ean")
    name: str = Field(faker="catch_phrase")  # Using catch_phrase as product name
    status: str = Field(faker="random_element", elements=["available", "discontinued"])
    price: float = Field(faker="pyfloat", positive=True, max_value=1000)


class ProductViewed(BaseEvent):
    user_id: str
    product_id: str
    viewed_at: datetime = Field(faker="date_time")


class AddToCart(BaseEvent):
    user_id: str
    product_id: str
    quantity: int = Field(faker="random_int", min=1, max=5)
    added_at: datetime = Field(faker="date_time")


class Purchase(BaseEvent):
    user_id: str
    product_id: str
    quantity: int
    total_amount: float
    purchased_at: datetime = Field(faker="date_time")


class OrderShipped(BaseEvent):
    order_id: str = Field(primary_key=True, faker="uuid4")
    user_id: str  # Should be populated from User entity
    product_id: str  # Should be populated from Product entity if available
    shipped_at: datetime = Field(faker="date_time")
    tracking_number: str = Field(faker="uuid4")


# Entities
class User(Entity):
    source_event = UserRegistered
    primary_key = "user_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    last_login: datetime = StateField(default=None, type_=datetime)
    total_purchases: int = StateField(default=0, type_=int)
    cart_items: int = StateField(default=0, type_=int)


class Product(Entity):
    source_event = ProductCreated
    primary_key = "product_id"

    current_status: str = StateField(from_field="status", type_=str)
    inventory: int = StateField(default=100, type_=int)
    view_count: int = StateField(default=0, type_=int)


def test_ecommerce_simulation():
    """Test complete e-commerce simulation."""
    # Create simulation
    sim = Simulation(
        duration="1m",  # Short duration for testing
        start_time="now",
        random_seed=42,
        initial_entities={
            User: 10,  # Start with 10 users
            Product: 5,  # Start with 5 products
        },
    )

    # Define flows
    @sim.flow(initiation_weight=3.0)
    def new_user_registration(ctx: Context):
        """New user registers and might log in."""
        yield NewEvent(ctx, UserRegistered, save_entity=User)
        yield AddDecay(ctx, rate=0.3, seconds=5)  # 30% chance to drop off
        yield NewEvent(
            ctx, UserLoggedIn, mutate=SetState(User, [("is_logged_in", "is", True)])
        )

    @sim.flow(
        initiation_weight=5.0, filter=Select(User, where=[("is_logged_in", "is", True)])
    )
    def user_browsing_session(ctx: Context):
        """Logged in user browses products."""
        # Select a random product for viewing
        yield NewEvent(ctx, ProductViewed, product_id="DUMMY_PRODUCT_ID")
        yield AddDecay(ctx, rate=0.4, seconds=10)

        # Maybe add to cart
        yield NewEvent(ctx, AddToCart, product_id="DUMMY_PRODUCT_ID", quantity=1)
        yield AddDecay(ctx, rate=0.6, seconds=15)

        # Maybe purchase
        yield NewEvent(
            ctx,
            Purchase,
            product_id="DUMMY_PRODUCT_ID",
            quantity=1,
            total_amount=99.99,
            mutate=SetState(User, [("total_purchases", "add", 1)]),
        )

    @sim.flow(initiation_weight=1.0)
    def new_product_creation(ctx: Context):
        """Create new products."""
        yield NewEvent(ctx, ProductCreated, save_entity=Product)

    # Capture output
    output_events = []

    class TestOutput:
        def send_event(self, event):
            output_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())

    # Run simulation
    sim.run()

    # Verify results
    assert len(output_events) > 0, "Should generate at least some events"

    # Check that we have different event types
    event_types = {type(event).__name__ for event in output_events}

    # Should have at least user and product events
    expected_types = {"UserRegistered", "ProductCreated"}
    assert expected_types.issubset(
        event_types
    ), f"Missing event types. Got: {event_types}"

    # Verify event data structure
    for event in output_events:
        event_dict = event.model_dump()
        assert isinstance(event_dict, dict)
        assert len(event_dict) > 0

    print(f"Generated {len(output_events)} events of types: {event_types}")


def test_multi_entity_ecommerce_flow():
    """Test e-commerce flow that works with both User and Product entities."""
    # Create simulation
    sim = Simulation(
        duration="30s",
        start_time="now",
        random_seed=42,
        initial_entities={User: 5, Product: 3},
    )

    # Define a flow that interacts with both users and products
    @sim.flow(
        initiation_weight=5.0,
        filter=Select(User, where=[("is_logged_in", "is", False)]),
    )
    def user_product_interaction(ctx: Context):
        """User logs in, views products, and completes purchase with shipping."""
        # User logs in
        yield NewEvent(
            ctx, UserLoggedIn, mutate=SetState(User, [("is_logged_in", "is", True)])
        )

        # Get a product from entity manager and add to context
        products = sim.entity_manager.get_entities(Product)
        if products:
            selected_product = products[0]  # Select first product
            ctx.add_entity(Product, selected_product)

        yield AddDecay(ctx, rate=0.2, seconds=5)

        # View the product
        yield NewEvent(ctx, ProductViewed)

        yield AddDecay(ctx, rate=0.3, seconds=10)

        # Purchase the product (both user and product entities are affected)
        yield NewEvent(
            ctx,
            Purchase,
            quantity=1,
            total_amount=49.99,
            mutate=SetState(User, [("total_purchases", "add", 1)]),
        )

        yield AddDecay(ctx, rate=0.4, seconds=15)

        # Ship the order (should have both user_id and product_id populated)
        yield NewEvent(ctx, OrderShipped)

    # Capture output
    output_events = []

    class TestOutput:
        def send_event(self, event):
            output_events.append(event)

        def close(self):
            pass

    sim.add_output(TestOutput())

    # Run simulation
    sim.run()

    # Verify results
    assert len(output_events) > 0, "Should generate events"

    # Check event types
    event_types = {type(event).__name__ for event in output_events}

    # Look for events that should have multiple entity IDs populated
    login_events = [e for e in output_events if type(e).__name__ == "UserLoggedIn"]
    purchase_events = [e for e in output_events if type(e).__name__ == "Purchase"]
    shipping_events = [e for e in output_events if type(e).__name__ == "OrderShipped"]

    # Verify that purchase events have proper user_id and product_id
    if purchase_events:
        purchase_event = purchase_events[0]
        assert hasattr(purchase_event, "user_id"), "Purchase should have user_id"
        assert hasattr(purchase_event, "product_id"), "Purchase should have product_id"
        assert (
            purchase_event.user_id is not None
        ), "Purchase user_id should be populated"
        assert (
            purchase_event.product_id is not None
        ), "Purchase product_id should be populated"

    # Verify that shipping events have both IDs populated
    if shipping_events:
        shipping_event = shipping_events[0]
        assert hasattr(shipping_event, "user_id"), "Shipping should have user_id"
        assert hasattr(shipping_event, "product_id"), "Shipping should have product_id"
        assert (
            shipping_event.user_id is not None
        ), "Shipping user_id should be populated"
        assert (
            shipping_event.product_id is not None
        ), "Shipping product_id should be populated"

    print(
        f"Multi-entity flow generated {len(output_events)} events of types: {event_types}"
    )

    # Verify that user states were updated
    users = sim.entity_manager.get_entities(User)
    logged_in_users = [u for u in users if u.is_logged_in]
    users_with_purchases = [u for u in users if u.total_purchases > 0]

    print(
        f"Logged in users: {len(logged_in_users)}, Users with purchases: {len(users_with_purchases)}"
    )

    # At least some users should have been affected
    assert (
        len(logged_in_users) > 0 or len(users_with_purchases) > 0
    ), "Some users should have been affected by the simulation"


def test_entity_state_management():
    """Test that entity states are properly managed."""
    # Create a user entity
    user_data = {
        "user_id": str(uuid.uuid4()),
        "full_name": "Test User",
        "email": "test@example.com",
        "registered_at": datetime.now(),
    }

    user = User(**user_data)

    # Test initial state
    assert not user.is_logged_in
    assert user.total_purchases == 0
    assert user.get_primary_key() == user_data["user_id"]

    # Test state updates
    user.update_state([("is_logged_in", "is", True)])
    assert user.is_logged_in

    user.update_state([("total_purchases", "add", 5)])
    assert user.total_purchases == 5

    user.update_state([("total_purchases", "subtract", 2)])
    assert user.total_purchases == 3


def test_product_entity():
    """Test product entity with from_field initialization."""
    product_data = {
        "product_id": "123456789",
        "name": "Test Product",
        "status": "available",
        "price": 29.99,
    }

    product = Product(**product_data)

    # Test from_field initialization
    assert product.current_status == "available"
    assert product.inventory == 100  # default value
    assert product.get_primary_key() == "123456789"


if __name__ == "__main__":
    test_ecommerce_simulation()
    test_multi_entity_ecommerce_flow()
    test_entity_state_management()
    test_product_entity()
    print("All E-commerce tests passed!")
