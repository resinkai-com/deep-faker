"""E-commerce simulation configuration."""

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
    StdOutOutput,
)


# Event Schemas
class UserRegistered(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    full_name: str = Field(faker="name")
    email: str = Field(faker="email")
    registered_at: datetime = Field(faker="now")


class UserLoggedIn(BaseEvent):
    user_id: str
    login_time: datetime = Field(faker="now")
    session_id: str = Field(faker="uuid4")


class ProductCreated(BaseEvent):
    product_id: str = Field(primary_key=True, faker="ean")
    name: str = Field(faker="catch_phrase")
    status: str = Field(faker="random_element", elements=["available", "discontinued"])
    price: float = Field(faker="pyfloat", positive=True, min_value=1, max_value=500)
    category: str = Field(
        faker="random_element", elements=["Electronics", "Clothing", "Books", "Home"]
    )


class ProductViewed(BaseEvent):
    user_id: str
    product_id: str
    viewed_at: datetime = Field(faker="now")
    view_duration: int = Field(faker="random_int", min=5, max=300)  # seconds


class AddToCart(BaseEvent):
    user_id: str
    product_id: str
    quantity: int = Field(faker="random_int", min=1, max=3)
    added_at: datetime = Field(faker="now")


class Purchase(BaseEvent):
    user_id: str
    product_id: str
    quantity: int
    unit_price: float
    total_amount: float
    purchased_at: datetime = Field(faker="now")
    payment_method: str = Field(
        faker="random_element", elements=["credit_card", "paypal", "apple_pay"]
    )


class ProductReview(BaseEvent):
    user_id: str
    product_id: str
    rating: int = Field(faker="random_int", min=1, max=5)
    review_text: str = Field(faker="text", max_nb_chars=200)
    reviewed_at: datetime = Field(faker="now")


# Entities
class User(Entity):
    source_event = UserRegistered
    primary_key = "user_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    last_login: datetime = StateField(default=None, type_=datetime)
    total_purchases: int = StateField(default=0, type_=int)
    cart_items: int = StateField(default=0, type_=int)
    total_spent: float = StateField(default=0.0, type_=float)


class Product(Entity):
    source_event = ProductCreated
    primary_key = "product_id"

    current_status: str = StateField(from_field="status", type_=str)
    current_price: float = StateField(from_field="price", type_=float)
    inventory: int = StateField(default=50, type_=int)
    view_count: int = StateField(default=0, type_=int)
    total_sales: int = StateField(default=0, type_=int)


# Create simulation
sim = Simulation(
    duration="5m",  # 5 minute simulation
    start_time="now",
    random_seed=42,
    initial_entities={
        User: 25,  # Start with 25 users
        Product: 15,  # Start with 15 products
    },
)


# Define flows
@sim.flow(initiation_weight=3.0)
def new_user_registration(ctx: Context):
    """A new user registers and might log in."""
    yield NewEvent(ctx, UserRegistered, save_entity=User)
    yield AddDecay(ctx, rate=0.2, seconds=10)  # 20% chance to drop off
    yield NewEvent(
        ctx,
        UserLoggedIn,
        mutate=SetState(
            User, [("is_logged_in", "is", True), ("last_login", "is", ctx.current_time)]
        ),
    )


@sim.flow(
    initiation_weight=8.0, filter=Select(User, where=[("is_logged_in", "is", True)])
)
def user_browsing_session(ctx: Context):
    """A logged-in user browses and might purchase products."""
    # Browse a product (use a dummy product ID for now)
    yield NewEvent(ctx, ProductViewed, product_id="PRODUCT_001")
    yield AddDecay(ctx, rate=0.3, seconds=15)

    # Maybe add to cart
    yield NewEvent(
        ctx,
        AddToCart,
        product_id="PRODUCT_001",
        mutate=SetState(User, [("cart_items", "add", 1)]),
    )
    yield AddDecay(ctx, rate=0.5, seconds=30)

    # Maybe purchase
    purchase_event = NewEvent(
        ctx,
        Purchase,
        product_id="PRODUCT_001",
        quantity=1,
        unit_price=99.99,
        total_amount=99.99,
        mutate=SetState(
            User,
            [
                ("total_purchases", "add", 1),
                ("cart_items", "subtract", 1),
                ("total_spent", "add", 99.99),
            ],
        ),
    )
    yield purchase_event
    yield AddDecay(ctx, rate=0.7, seconds=60)

    # Maybe leave a review
    yield NewEvent(ctx, ProductReview, product_id="PRODUCT_001")


@sim.flow(
    initiation_weight=5.0, filter=Select(User, where=[("is_logged_in", "is", False)])
)
def returning_user_login(ctx: Context):
    """An existing user logs in."""
    yield NewEvent(
        ctx,
        UserLoggedIn,
        mutate=SetState(
            User, [("is_logged_in", "is", True), ("last_login", "is", ctx.current_time)]
        ),
    )


@sim.flow(initiation_weight=1.5)
def new_product_listing(ctx: Context):
    """New products get added to the catalog."""
    yield NewEvent(ctx, ProductCreated, save_entity=Product)


# Configure outputs
sim.add_output(StdOutOutput())

# The simulation will be run by the CLI
if __name__ == "__main__":
    print("E-commerce Simulation")
    print("====================")
    sim.run()
