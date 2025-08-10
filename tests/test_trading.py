"""End-to-end test for Trading platform event simulation."""

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
class TraderRegistered(BaseEvent):
    trader_id: str = Field(primary_key=True, faker="uuid4")
    username: str = Field(faker="user_name")
    email: str = Field(faker="email")
    initial_balance: float = Field(faker="pyfloat", min_value=1000, max_value=100000)
    registered_at: datetime = Field(faker="date_time_this_decade")


class TraderLoggedIn(BaseEvent):
    trader_id: str
    session_id: str = Field(faker="uuid4")
    login_time: datetime = Field(faker="date_time")


class StockListed(BaseEvent):
    symbol: str = Field(
        primary_key=True, faker="lexify", text="????"
    )  # 4 letter stock symbol
    company_name: str = Field(faker="company")
    initial_price: float = Field(faker="pyfloat", min_value=10, max_value=1000)
    listed_at: datetime = Field(faker="date_time")


class PriceUpdate(BaseEvent):
    symbol: str
    new_price: float = Field(faker="pyfloat", min_value=5, max_value=2000)
    change_percent: float = Field(faker="pyfloat", min_value=-10, max_value=10)
    volume: int = Field(faker="random_int", min=100, max=10000)
    updated_at: datetime = Field(faker="date_time")


class MarketOrder(BaseEvent):
    order_id: str = Field(primary_key=True, faker="uuid4")
    trader_id: str
    symbol: str
    order_type: str = Field(faker="random_element", elements=["BUY", "SELL"])
    quantity: int = Field(faker="random_int", min=1, max=1000)
    price: float
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
    filled_at: datetime = Field(faker="date_time")


class PortfolioUpdate(BaseEvent):
    trader_id: str
    symbol: str
    new_quantity: int
    new_balance: float
    updated_at: datetime = Field(faker="date_time")


# Entities
class Trader(Entity):
    source_event = TraderRegistered
    primary_key = "trader_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    current_balance: float = StateField(from_field="initial_balance", type_=float)
    total_trades: int = StateField(default=0, type_=int)
    active_orders: int = StateField(default=0, type_=int)


class Stock(Entity):
    source_event = StockListed
    primary_key = "symbol"

    current_price: float = StateField(from_field="initial_price", type_=float)
    daily_volume: int = StateField(default=0, type_=int)
    price_changes: int = StateField(default=0, type_=int)


class Order(Entity):
    source_event = MarketOrder
    primary_key = "order_id"

    current_status: str = StateField(from_field="status", type_=str)
    fill_quantity: int = StateField(default=0, type_=int)


def test_trading_simulation():
    """Test complete trading platform simulation."""
    # Create simulation
    sim = Simulation(
        duration="30s",  # Very short duration for testing
        start_time="now",
        random_seed=123,
        initial_entities={
            Trader: 5,  # Start with 5 traders
            Stock: 10,  # Start with 10 stocks
        },
    )

    # Define flows
    @sim.flow(initiation_weight=2.0)
    def new_trader_onboarding(ctx: Context):
        """New trader registers and logs in."""
        yield NewEvent(ctx, TraderRegistered, save_entity=Trader)
        yield AddDecay(ctx, rate=0.2, seconds=2)
        yield NewEvent(
            ctx, TraderLoggedIn, mutate=SetState(Trader, [("is_logged_in", "is", True)])
        )

    @sim.flow(initiation_weight=1.0)
    def new_stock_listing(ctx: Context):
        """New stock gets listed on the platform."""
        yield NewEvent(ctx, StockListed, save_entity=Stock)

    @sim.flow(initiation_weight=8.0)
    def market_price_updates(ctx: Context):
        """Regular price updates for stocks."""
        yield NewEvent(ctx, PriceUpdate, symbol="DUMMY")
        yield AddDecay(ctx, rate=0.1, seconds=1)

    @sim.flow(
        initiation_weight=6.0,
        filter=Select(Trader, where=[("is_logged_in", "is", True)]),
    )
    def trader_activity(ctx: Context):
        """Active trader places orders."""
        # Place an order
        yield NewEvent(
            ctx,
            MarketOrder,
            save_entity=Order,
            symbol="DUMMY",
            price=100.0,
            mutate=SetState(Trader, [("active_orders", "add", 1)]),
        )
        yield AddDecay(ctx, rate=0.4, seconds=3)

        # Maybe fill the order
        yield NewEvent(
            ctx,
            OrderFilled,
            order_id="DUMMY_ORDER",
            symbol="DUMMY",
            quantity=10,
            fill_price=101.0,
            total_amount=1010.0,
            mutate=SetState(
                Trader, [("total_trades", "add", 1), ("active_orders", "subtract", 1)]
            ),
        )

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

    # Should have at least trader and stock events
    expected_types = {"TraderRegistered", "StockListed"}
    assert expected_types.issubset(
        event_types
    ), f"Missing event types. Got: {event_types}"

    # Verify event data structure
    for event in output_events:
        event_dict = event.model_dump()
        assert isinstance(event_dict, dict)
        assert len(event_dict) > 0

    print(f"Generated {len(output_events)} trading events of types: {event_types}")


def test_trader_state_management():
    """Test that trader states are properly managed."""
    # Create a trader entity
    trader_data = {
        "trader_id": str(uuid.uuid4()),
        "username": "testtrader",
        "email": "trader@example.com",
        "initial_balance": 10000.0,
        "registered_at": datetime.now(),
    }

    trader = Trader(**trader_data)

    # Test initial state
    assert trader.is_logged_in == False
    assert trader.current_balance == 10000.0
    assert trader.total_trades == 0
    assert trader.active_orders == 0
    assert trader.get_primary_key() == trader_data["trader_id"]

    # Test state updates
    trader.update_state(
        [
            ("is_logged_in", "is", True),
            ("active_orders", "add", 3),
            ("current_balance", "subtract", 500.0),
        ]
    )

    assert trader.is_logged_in == True
    assert trader.active_orders == 3
    assert trader.current_balance == 9500.0


def test_stock_entity():
    """Test stock entity with price tracking."""
    stock_data = {
        "symbol": "AAPL",
        "company_name": "Apple Inc.",
        "initial_price": 150.0,
        "listed_at": datetime.now(),
    }

    stock = Stock(**stock_data)

    # Test from_field initialization
    assert stock.current_price == 150.0
    assert stock.daily_volume == 0  # default value
    assert stock.price_changes == 0  # default value
    assert stock.get_primary_key() == "AAPL"

    # Test price updates
    stock.update_state(
        [
            ("current_price", "is", 155.0),
            ("daily_volume", "add", 1000),
            ("price_changes", "add", 1),
        ]
    )

    assert stock.current_price == 155.0
    assert stock.daily_volume == 1000
    assert stock.price_changes == 1


def test_order_entity():
    """Test order entity lifecycle."""
    order_data = {
        "order_id": str(uuid.uuid4()),
        "trader_id": str(uuid.uuid4()),
        "symbol": "TSLA",
        "order_type": "BUY",
        "quantity": 100,
        "price": 200.0,
        "status": "PENDING",
        "created_at": datetime.now(),
    }

    order = Order(**order_data)

    # Test initial state
    assert order.current_status == "PENDING"
    assert order.fill_quantity == 0
    assert order.get_primary_key() == order_data["order_id"]

    # Test order fulfillment
    order.update_state(
        [("current_status", "is", "FILLED"), ("fill_quantity", "is", 100)]
    )

    assert order.current_status == "FILLED"
    assert order.fill_quantity == 100


if __name__ == "__main__":
    test_trading_simulation()
    test_trader_state_management()
    test_stock_entity()
    test_order_entity()
    print("All Trading platform tests passed!")
