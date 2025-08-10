"""Realistic E-commerce simulation configuration based on standard events taxonomy."""

from datetime import datetime
from typing import Optional

from deep_faker import (
    AddDecay,
    BaseEvent,
    Entity,
    Field,
    NewEvent,
    Select,
    SetState,
    Simulation,
    StateField,
    StdOutOutput,
)
from deep_faker.actions import FlowContext


# Event Schemas
class AccountCreated(BaseEvent):
    """When the user successfully creates their account."""

    user_id: str = Field(primary_key=True, faker="uuid4")
    account_creation_date: str = Field(faker="date")  # YYYY-MM-DD format
    account_type: str = Field(
        faker="random_element", elements=["email", "facebook", "twitter"]
    )
    email: str = Field(faker="email")
    full_name: str = Field(faker="name")


class Search(BaseEvent):
    """Triggered after 3 characters have been entered."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    search_id: str = Field(faker="uuid4")
    keywords: str = Field(
        faker="random_element",
        elements=["shoes", "jeans", "dress", "jacket", "shirt", "pants"],
    )
    number_of_results: int = Field(faker="random_int", min=0, max=50)
    search_timestamp: datetime = Field(faker="now")


class ProductClicked(BaseEvent):
    """When a user clicks on a product."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    product_id: str
    product_name: str
    price: float
    rank: int = Field(faker="random_int", min=1, max=10)  # Rank in search results
    page_source: str = Field(
        faker="random_element",
        elements=["search", "homepage", "category", "recommendations"],
    )
    clicked_at: datetime = Field(faker="now")


class ProductDetailsViewed(BaseEvent):
    """When a user views the details of a product."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    product_id: str
    page_source: str = Field(
        faker="random_element",
        elements=["discover feed", "wishlist", "search", "category"],
    )
    view_duration: int = Field(faker="random_int", min=5, max=300)  # seconds
    viewed_at: datetime = Field(faker="now")


class ProductAdded(BaseEvent):
    """When a user adds a product to their cart."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    product_id: str
    cart_id: str
    quantity: int = Field(faker="random_int", min=1, max=3)
    unit_price: float
    added_at: datetime = Field(faker="now")


class CheckoutStarted(BaseEvent):
    """When a user starts the checkout process."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    cart_id: str
    cart_total: float
    cart_size: int  # Number of items
    coupon_code: Optional[str] = Field(
        default=None,
        faker="random_element",
        elements=[None, "BOGO2021", "50%off", "SUMMER25"],
    )
    started_at: datetime = Field(faker="now")


class ProductRemoved(BaseEvent):
    """When a user removes a product from their cart."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    product_id: str
    cart_id: str
    quantity_removed: int = Field(faker="random_int", min=1, max=3)
    removed_at: datetime = Field(faker="now")


class ShippingInfoAdded(BaseEvent):
    """When a user adds their shipping information."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    order_id: str = Field(faker="uuid4")
    shipping_method: str = Field(
        faker="random_element", elements=["express", "standard", "overnight"]
    )
    shipping_cost: float = Field(
        faker="pyfloat", min_value=0, max_value=25.99, positive=True
    )
    added_at: datetime = Field(faker="now")


class PaymentInfoAdded(BaseEvent):
    """When a user adds their payment information."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    order_id: str
    payment_method: str = Field(
        faker="random_element", elements=["credit", "apple pay", "paypal"]
    )
    added_at: datetime = Field(faker="now")


class OrderCompleted(BaseEvent):
    """When a user successfully completes an order."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    order_id: str
    order_total: float  # Including tax and shipping
    revenue: float  # Subtotal
    tax: float
    shipping_cost: float
    discount_amount: float = Field(default=0.0)
    item_count: int
    completed_at: datetime = Field(faker="now")


class OrderEdited(BaseEvent):
    """When a user makes changes to their order."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    order_id: str
    fields_modified: str = Field(
        faker="random_element",
        elements=["quantity", "shipping_address", "payment_method"],
    )
    edited_at: datetime = Field(faker="now")


class OrderCancelled(BaseEvent):
    """When an order is cancelled before the item is received."""

    user_id: str
    session_id: str = Field(faker="uuid4")
    order_id: str
    reason: str = Field(
        faker="random_element",
        elements=["missed delivery", "out-of-stock", "backorder", "customer_request"],
    )
    cancelled_at: datetime = Field(faker="now")


class ErrorTriggered(BaseEvent):
    """When an error is encountered anywhere in the browse or checkout flow."""

    user_id: Optional[str] = None  # May not have user context
    session_id: str = Field(faker="uuid4")
    error_code: str = Field(
        faker="random_element",
        elements=[
            "PAYMENT_FAILED",
            "INVENTORY_ERROR",
            "NETWORK_TIMEOUT",
            "VALIDATION_ERROR",
        ],
    )
    error_message: str = Field(
        faker="random_element",
        elements=[
            "Payment processing failed",
            "Item out of stock",
            "Connection timeout",
            "Invalid input",
        ],
    )
    page: str = Field(
        faker="random_element", elements=["checkout", "product_page", "cart", "search"]
    )
    occurred_at: datetime = Field(faker="now")


class ProductListed(BaseEvent):
    """When a new product is added to the catalog."""

    product_id: str = Field(primary_key=True, faker="lexify", text="PROD_????")
    name: str = Field(
        faker="random_element",
        elements=[
            "Running Shoes",
            "Blue Jeans",
            "Summer Dress",
            "Leather Jacket",
            "Cotton Shirt",
            "Casual Pants",
            "Winter Coat",
            "Sneakers",
        ],
    )
    price: float = Field(
        faker="pyfloat", min_value=19.99, max_value=199.99, positive=True
    )
    category: str = Field(
        faker="random_element",
        elements=["shoes", "jeans", "dress", "jacket", "shirt", "pants"],
    )
    listed_at: datetime = Field(faker="now")


# Entities
class User(Entity):
    """User entity tracking account and session state."""

    source_event = AccountCreated
    primary_key = "user_id"

    account_type: str = StateField(from_field="account_type", type_=str)
    is_logged_in: bool = StateField(default=False, type_=bool)
    current_session_id: Optional[str] = StateField(default=None, type_=str)
    cart_id: Optional[str] = StateField(default=None, type_=str)
    total_orders: int = StateField(default=0, type_=int)
    total_spent: float = StateField(default=0.0, type_=float)
    last_search_keywords: Optional[str] = StateField(default=None, type_=str)


class Product(Entity):
    """Product entity tracking inventory and popularity."""

    source_event = ProductListed
    primary_key = "product_id"

    name: str = StateField(from_field="name", type_=str)
    price: float = StateField(from_field="price", type_=float)
    category: str = StateField(from_field="category", type_=str)
    inventory_count: int = StateField(default=100, type_=int)
    view_count: int = StateField(default=0, type_=int)
    click_count: int = StateField(default=0, type_=int)
    cart_additions: int = StateField(default=0, type_=int)
    total_sales: int = StateField(default=0, type_=int)


class Cart(Entity):
    """Shopping cart entity tracking items and state."""

    source_event = None  # Carts are created when first product is added
    primary_key = "cart_id"

    user_id: str = StateField(type_=str)
    item_count: int = StateField(default=0, type_=int)
    total_value: float = StateField(default=0.0, type_=float)
    checkout_started: bool = StateField(default=False, type_=bool)
    last_updated: Optional[datetime] = StateField(default=None, type_=datetime)


class Order(Entity):
    """Order entity tracking purchase process."""

    source_event = CheckoutStarted
    primary_key = "order_id"

    user_id: str = StateField(type_=str)
    cart_id: str = StateField(type_=str)
    status: str = StateField(
        default="pending", type_=str
    )  # pending, completed, cancelled
    has_shipping_info: bool = StateField(default=False, type_=bool)
    has_payment_info: bool = StateField(default=False, type_=bool)
    total_amount: float = StateField(default=0.0, type_=float)


# Create simulation
sim = Simulation(
    duration="5m",  # 5 minute simulation for testing
    start_time="now",
    random_seed=42,
    initial_entities={
        User: 25,  # Start with 25 registered users
        Product: 8,  # Start with 8 products
    },
    n_flows=2,  # Allow multiple concurrent flows
)


# Define flows
@sim.flow(initiation_weight=2.0)
def new_user_registration(ctx: FlowContext):
    """A new user creates an account."""
    yield NewEvent(ctx, AccountCreated, save_entity=User)


@sim.flow(
    initiation_weight=5.0, filter=Select(User, where=[("is_logged_in", "is", False)])
)
def user_login_and_search(ctx: FlowContext):
    """User logs in and searches for products."""
    # Start a session (implicit login)
    session_id = f"sess_{ctx.session_id[:8]}"

    # Update user state for login
    yield NewEvent(
        ctx,
        Search,
        session_id=session_id,
        mutate=SetState(
            User,
            [("is_logged_in", "is", True), ("current_session_id", "is", session_id)],
        ),
    )


@sim.flow(
    initiation_weight=8.0, filter=Select(User, where=[("is_logged_in", "is", True)])
)
def product_browsing_flow(ctx: FlowContext):
    """User browses and clicks on products."""
    user = ctx.get_entity(User)
    if not user:
        return

    # Get a random product
    products = ctx.global_context.get_entities(Product)
    if not products:
        return

    import random

    product = random.choice(products)

    # Click on product
    yield NewEvent(
        ctx,
        ProductClicked,
        session_id=user.current_session_id,
        product_id=product.get_primary_key(),
        product_name=product.name,
        price=product.price,
        mutate=SetState(Product, [("click_count", "add", 1)]),
    )

    yield AddDecay(ctx, rate=0.3, seconds=5)

    # View product details
    yield NewEvent(
        ctx,
        ProductDetailsViewed,
        session_id=user.current_session_id,
        product_id=product.get_primary_key(),
        mutate=SetState(Product, [("view_count", "add", 1)]),
    )


@sim.flow(
    initiation_weight=6.0, filter=Select(User, where=[("is_logged_in", "is", True)])
)
def add_to_cart_flow(ctx: FlowContext):
    """User adds products to cart."""
    user = ctx.get_entity(User)
    if not user:
        return

    # Get or create cart
    cart_id = user.cart_id
    if not cart_id:
        cart_id = f"cart_{ctx.session_id[:8]}"

    # Get a random product
    products = ctx.global_context.get_entities(Product)
    if not products:
        return

    import random

    product = random.choice(products)
    quantity = random.randint(1, 3)

    # Add to cart
    yield NewEvent(
        ctx,
        ProductAdded,
        session_id=user.current_session_id,
        product_id=product.get_primary_key(),
        cart_id=cart_id,
        quantity=quantity,
        unit_price=product.price,
        mutate=SetState(User, [("cart_id", "is", cart_id)]),
    )


@sim.flow(
    initiation_weight=4.0, filter=Select(User, where=[("cart_id", "is_not", None)])
)
def checkout_flow(ctx: FlowContext):
    """User goes through checkout process."""
    user = ctx.get_entity(User)
    if not user or not user.cart_id:
        return

    # Start checkout
    cart_total = 150.0 + (hash(user.cart_id) % 100)  # Simulated cart total
    cart_size = (hash(user.cart_id) % 3) + 1

    order_id = f"order_{ctx.session_id[:8]}"

    yield NewEvent(
        ctx,
        CheckoutStarted,
        session_id=user.current_session_id,
        cart_id=user.cart_id,
        cart_total=cart_total,
        cart_size=cart_size,
        save_entity=Order,
    )

    yield AddDecay(ctx, rate=0.4, seconds=30)  # 40% abandon at checkout

    # Add shipping info
    yield NewEvent(
        ctx,
        ShippingInfoAdded,
        session_id=user.current_session_id,
        order_id=order_id,
        mutate=SetState(Order, [("has_shipping_info", "is", True)]),
    )

    yield AddDecay(ctx, rate=0.3, seconds=15)

    # Add payment info
    yield NewEvent(
        ctx,
        PaymentInfoAdded,
        session_id=user.current_session_id,
        order_id=order_id,
        mutate=SetState(Order, [("has_payment_info", "is", True)]),
    )

    yield AddDecay(ctx, rate=0.2, seconds=10)

    # Complete order
    revenue = cart_total * 0.9  # Before tax
    tax = revenue * 0.08
    shipping = 8.99

    yield NewEvent(
        ctx,
        OrderCompleted,
        session_id=user.current_session_id,
        order_id=order_id,
        order_total=cart_total,
        revenue=revenue,
        tax=tax,
        shipping_cost=shipping,
        item_count=cart_size,
        mutate=SetState(
            User,
            [
                ("total_orders", "add", 1),
                ("total_spent", "add", cart_total),
                ("cart_id", "is", None),  # Clear cart
            ],
        ),
    )


@sim.flow(initiation_weight=1.5)
def error_flow(ctx: FlowContext):
    """Simulate various errors that can occur."""
    user = ctx.get_entity(User) if ctx.selected_entities else None
    user_id = user.get_primary_key() if user else None

    yield NewEvent(ctx, ErrorTriggered, user_id=user_id)


@sim.flow(
    initiation_weight=1.0,
    filter=Select(User, where=[("total_orders", "greater_than", 0)]),
)
def order_management_flow(ctx: FlowContext):
    """Existing customers might edit or cancel orders."""
    user = ctx.get_entity(User)
    if not user:
        return

    order_id = f"order_{ctx.session_id[:8]}"

    # 70% chance to edit, 30% to cancel
    import random

    if random.random() < 0.7:
        yield NewEvent(
            ctx,
            OrderEdited,
            session_id=user.current_session_id or f"sess_{ctx.session_id[:8]}",
            order_id=order_id,
        )
    else:
        yield NewEvent(
            ctx,
            OrderCancelled,
            session_id=user.current_session_id or f"sess_{ctx.session_id[:8]}",
            order_id=order_id,
        )


# Configure outputs
sim.add_output(StdOutOutput())

# The simulation will be run by the CLI
if __name__ == "__main__":
    print("Realistic E-commerce Simulation")
    print("==============================")
    print("Based on standard e-commerce events taxonomy")
    print()
    sim.run()
