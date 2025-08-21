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
    StdOutOutput,
)
from deep_faker.logging import get_logger
from deep_faker.outputs import FileOutput, KafkaOutput


# 1. Define Event Schemas
class UserRegistered(BaseEvent):
    """Event triggered when a new user creates an account."""

    user_id: str = Field(primary_key=True, faker="uuid4")
    email: str = Field(faker="email")
    full_name: str = Field(faker="name")
    registration_date: datetime = Field(faker="now")


class ProductCreatedOrUpdated(BaseEvent):
    """Event for creating a new product or updating its details."""

    product_id: str = Field(primary_key=True, faker="lexify", text="PROD-??????")
    name: str = Field(
        faker="random_element", elements=["Laptop", "Mouse", "Keyboard", "Monitor"]
    )
    price: float = Field(faker="pyfloat", min_value=50.0, max_value=2000.0)
    inventory: int = Field(faker="random_int", min=50, max=200)


class ProductPurchased(BaseEvent):
    """Event fired when a user completes a purchase."""

    order_id: str = Field(faker="uuid4")
    user_id: str
    product_id: str
    quantity: int = Field(faker="random_int", min=1, max=2)
    total_price: float


# 2. Define Entities with State
class User(Entity):
    """Represents a user and their state in the system."""

    source_event = UserRegistered
    primary_key = "user_id"

    # State fields to track user activity
    email: str = StateField(from_field="email", type_=str)
    is_active: bool = StateField(default=True, type_=bool)
    purchase_count: int = StateField(default=0, type_=int)


class Product(Entity):
    """Represents a product and its inventory."""

    source_event = ProductCreatedOrUpdated
    primary_key = "product_id"

    # State fields to track product details
    name: str = StateField(from_field="name", type_=str)
    price: float = StateField(from_field="price", type_=float)
    inventory: int = StateField(from_field="inventory", type_=int)


# 3. Create Simulation
sim = Simulation(
    duration="1m",  # Run for 1 minute
    start_time="now",
    n_flows=2,  # Number of concurrent user journeys
    initial_entities={
        User: 5,  # Start with 5 pre-existing users
        Product: 10,  # Start with 10 pre-existing products
    },
)


# 4. Define the User Purchase Flow
@sim.flow(
    initiation_weight=10.0,
    filter=Select(
        User, where=[("is_active", "is", True)]
    ),  # Only active users can start this flow
)
def user_purchase_flow(ctx: FlowContext):
    """
    A flow that models a user registering and immediately
    purchasing a randomly selected product.
    """
    # Get the user and a random product for this flow
    user = ctx.get_selected_entity(User)
    product = ctx.global_context.get_random_available_entity(
        Product
    )  # Select an available product

    # If no product is available, end the flow
    if not product:
        return

    purchase_quantity = 1
    total_price = product.price * purchase_quantity

    logger = get_logger(__name__)
    logger.info(
        f"Flow started for User '{user.get_primary_key()}' purchasing Product '{product.get_primary_key()}'"
    )

    # A short delay to simulate browsing before purchase
    yield AddDecay(ctx, rate=0.0, seconds=15)  # 10% drop-off chance over 15 seconds

    # Generate the purchase event and update entity states
    yield NewEvent(
        ctx,
        ProductPurchased,
        user_id=user.get_primary_key(),
        product_id=product.get_primary_key(),
        quantity=purchase_quantity,
        total_price=total_price,
        # Use mutate to update the state of both the User and Product
        mutate=[
            SetState(User, [("purchase_count", "add", 1)]),
            SetState(Product, [("inventory", "subtract", purchase_quantity)]),
        ],
    )


# 5. Configure Outputs
sim.add_output(StdOutOutput())
sim.add_output(FileOutput("output/E03_user_purchase_product.jsonl"))
sim.add_output(
    KafkaOutput(
        topic_mapping={
            ProductPurchased: "e03-product-purchased",
            UserRegistered: "e03-user-registered",
            ProductCreatedOrUpdated: "e03-product-created-or-updated",
        },
        bootstrap_servers="localhost:9092",
    )
)


# 6. Run Simulation
if __name__ == "__main__":
    sim.run()
