"""Trading platform simulation configuration."""

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
    StdOutOutput,
)


# Event Schemas
class TraderRegistered(BaseEvent):
    trader_id: str = Field(primary_key=True, faker="uuid4")
    username: str = Field(faker="user_name")
    email: str = Field(faker="email")
    initial_balance: float = Field(faker="pyfloat", min_value=1000, max_value=50000)
    registered_at: datetime = Field(faker="date_time_this_decade")
    country: str = Field(faker="country")


class TraderLoggedIn(BaseEvent):
    trader_id: str
    session_id: str = Field(faker="uuid4")
    login_time: datetime = Field(faker="date_time")
    platform: str = Field(faker="random_element", elements=["web", "mobile", "desktop"])


class StockListed(BaseEvent):
    symbol: str = Field(
        primary_key=True, faker="lexify", text="????"
    )  # 4 letter symbol
    company_name: str = Field(faker="company")
    initial_price: float = Field(faker="pyfloat", min_value=10, max_value=500)
    sector: str = Field(
        faker="random_element",
        elements=["Tech", "Finance", "Healthcare", "Energy", "Consumer"],
    )
    market_cap: str = Field(faker="random_element", elements=["Small", "Mid", "Large"])
    listed_at: datetime = Field(faker="date_time")


class PriceUpdate(BaseEvent):
    symbol: str
    old_price: float
    new_price: float = Field(faker="pyfloat", min_value=5, max_value=1000)
    change_percent: float = Field(faker="pyfloat", min_value=-15, max_value=15)
    volume: int = Field(faker="random_int", min=100, max=50000)
    updated_at: datetime = Field(faker="date_time")


class MarketOrder(BaseEvent):
    order_id: str = Field(primary_key=True, faker="uuid4")
    trader_id: str
    symbol: str
    order_type: str = Field(faker="random_element", elements=["BUY", "SELL"])
    quantity: int = Field(faker="random_int", min=1, max=500)
    price: float
    order_kind: str = Field(
        faker="random_element", elements=["MARKET", "LIMIT", "STOP"]
    )
    status: str = Field(
        faker="random_element", elements=["PENDING", "FILLED", "CANCELLED"]
    )
    created_at: datetime = Field(faker="date_time")


class OrderFilled(BaseEvent):
    order_id: str
    trader_id: str
    symbol: str
    quantity: int
    fill_price: float
    total_amount: float
    commission: float = Field(faker="pyfloat", min_value=1, max_value=50)
    filled_at: datetime = Field(faker="date_time")


class PortfolioUpdate(BaseEvent):
    trader_id: str
    symbol: str
    position_change: int
    new_position: int
    new_balance: float
    updated_at: datetime = Field(faker="date_time")


class MarketAlert(BaseEvent):
    trader_id: str
    symbol: str
    alert_type: str = Field(
        faker="random_element", elements=["PRICE_TARGET", "VOLUME_SPIKE", "NEWS"]
    )
    message: str = Field(faker="sentence")
    triggered_at: datetime = Field(faker="date_time")


# Entities
class Trader(Entity):
    source_event = TraderRegistered
    primary_key = "trader_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    current_balance: float = StateField(from_field="initial_balance", type_=float)
    total_trades: int = StateField(default=0, type_=int)
    active_orders: int = StateField(default=0, type_=int)
    profit_loss: float = StateField(default=0.0, type_=float)


class Stock(Entity):
    source_event = StockListed
    primary_key = "symbol"

    current_price: float = StateField(from_field="initial_price", type_=float)
    daily_volume: int = StateField(default=0, type_=int)
    price_changes: int = StateField(default=0, type_=int)
    total_orders: int = StateField(default=0, type_=int)


class Order(Entity):
    source_event = MarketOrder
    primary_key = "order_id"

    current_status: str = StateField(from_field="status", type_=str)
    fill_quantity: int = StateField(default=0, type_=int)
    remaining_quantity: int = StateField(from_field="quantity", type_=int)


# Create simulation
sim = Simulation(
    duration="3m",  # 3 minute simulation
    start_time="now",
    random_seed=123,
    initial_entities={
        Trader: 15,  # Start with 15 traders
        Stock: 25,  # Start with 25 stocks
    },
)


# Define flows
@sim.flow(initiation_weight=2.0)
def new_trader_onboarding(ctx: Context):
    """A new trader registers and logs in."""
    yield NewEvent(ctx, TraderRegistered, save_entity=Trader)
    yield AddDecay(ctx, rate=0.1, seconds=5)
    yield NewEvent(
        ctx, TraderLoggedIn, mutate=SetState(Trader, [("is_logged_in", "is", True)])
    )


@sim.flow(initiation_weight=1.0)
def new_stock_listing(ctx: Context):
    """New stock gets listed on the exchange."""
    yield NewEvent(ctx, StockListed, save_entity=Stock)


@sim.flow(initiation_weight=12.0)
def market_price_movements(ctx: Context):
    """Regular price updates for stocks."""
    # Price update
    yield NewEvent(ctx, PriceUpdate, symbol="AAPL", old_price=100.0)
    yield AddDecay(ctx, rate=0.05, seconds=2)


@sim.flow(
    initiation_weight=8.0, filter=Select(Trader, where=[("is_logged_in", "is", True)])
)
def active_trading_session(ctx: Context):
    """Active trader places orders and trades."""
    # Place an order
    yield NewEvent(
        ctx,
        MarketOrder,
        save_entity=Order,
        symbol="AAPL",
        price=150.0,
        mutate=SetState(Trader, [("active_orders", "add", 1)]),
    )
    yield AddDecay(ctx, rate=0.3, seconds=10)

    # Maybe fill the order
    yield NewEvent(
        ctx,
        OrderFilled,
        order_id="ORDER_001",
        symbol="AAPL",
        quantity=50,
        fill_price=151.0,
        total_amount=7550.0,
        mutate=SetState(
            Trader,
            [
                ("total_trades", "add", 1),
                ("active_orders", "subtract", 1),
                ("current_balance", "subtract", 7600.0),  # Include commission
            ],
        ),
    )
    yield AddDecay(ctx, rate=0.4, seconds=15)

    # Update portfolio
    yield NewEvent(
        ctx,
        PortfolioUpdate,
        symbol="AAPL",
        position_change=50,
        new_position=50,
        new_balance=42400.0,
    )


@sim.flow(
    initiation_weight=6.0, filter=Select(Trader, where=[("is_logged_in", "is", False)])
)
def returning_trader_login(ctx: Context):
    """Existing trader logs back in."""
    yield NewEvent(
        ctx, TraderLoggedIn, mutate=SetState(Trader, [("is_logged_in", "is", True)])
    )


@sim.flow(
    initiation_weight=4.0, filter=Select(Trader, where=[("is_logged_in", "is", True)])
)
def market_monitoring(ctx: Context):
    """Trader receives market alerts."""
    yield NewEvent(ctx, MarketAlert, symbol="AAPL")
    yield AddDecay(ctx, rate=0.8, seconds=30)


# Configure outputs
sim.add_output(StdOutOutput())

# The simulation will be run by the CLI
if __name__ == "__main__":
    print("Trading Platform Simulation")
    print("==========================")
    sim.run()
