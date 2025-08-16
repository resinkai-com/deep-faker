# Deep Faker: Python-Native Event Simulation User Guide

Deep Faker is a declarative event simulation library that allows you to create realistic, stateful event streams using Python. This guide demonstrates how to build complex simulations through simple, declarative flows.

## Quick Start: Complete Example

Here's a complete e-commerce simulation that demonstrates all core concepts:

```python
from datetime import datetime
from deep_faker import (
    BaseEvent, Entity, Field, StateField, Simulation,
    NewEvent, AddDecay, Select, SetState, FlowContext,
    StdOutOutput, FileOutput
)

# 1. Define Event Schemas
class AccountCreated(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    email: str = Field(faker="email")
    full_name: str = Field(faker="name")

class ProductAdded(BaseEvent):
    user_id: str
    product_id: str
    cart_id: str
    quantity: int = Field(faker="random_int", min=1, max=3)

class OrderCompleted(BaseEvent):
    user_id: str
    order_id: str
    total_amount: float

# 2. Define Entities with State
class User(Entity):
    source_event = AccountCreated
    primary_key = "user_id"

    is_logged_in: bool = StateField(default=False, type_=bool)
    cart_id: str = StateField(default=None, type_=str)
    total_orders: int = StateField(default=0, type_=int)

class Product(Entity):
    source_event = None  # Will be created during initialization
    primary_key = "product_id"

    name: str = StateField(type_=str)
    price: float = StateField(type_=float)
    inventory: int = StateField(default=100, type_=int)

# 3. Create Simulation
sim = Simulation(
    duration="2m",
    start_time="now",
    n_flows=3,
    initial_entities={User: 10, Product: 5}
)

# 4. Define Flows (Business Logic)
@sim.flow(initiation_weight=3.0)
def new_user_registration(ctx: FlowContext):
    """New users register and may browse products."""
    yield NewEvent(ctx, AccountCreated, save_entity=User)
    yield AddDecay(ctx, rate=0.2, seconds=30)  # 20% drop-off

    # User logs in
    yield NewEvent(
        ctx, ProductAdded,
        mutate=SetState(User, [("is_logged_in", "is", True)])
    )

@sim.flow(
    initiation_weight=5.0,
    filter=Select(User, where=[("is_logged_in", "is", True)])
)
def shopping_flow(ctx: FlowContext):
    """Logged-in users add products and complete orders."""
    user = ctx.get_entity(User)
    cart_id = f"cart_{ctx.session_id[:8]}"

    # Add product to cart
    yield NewEvent(
        ctx, ProductAdded,
        cart_id=cart_id,
        product_id="PROD_001",
        mutate=SetState(User, [("cart_id", "is", cart_id)])
    )

    yield AddDecay(ctx, rate=0.4, seconds=60)  # 40% abandon cart

    # Complete order
    yield NewEvent(
        ctx, OrderCompleted,
        order_id=f"order_{ctx.session_id[:8]}",
        total_amount=99.99,
        mutate=SetState(User, [("total_orders", "add", 1)])
    )

# 5. Configure Outputs
sim.add_output(StdOutOutput())
sim.add_output(FileOutput("simulation_events.jsonl"))

# 6. Run Simulation
if __name__ == "__main__":
    sim.run()
```

This example demonstrates:

- **Events**: Structured data models with fake data generation
- **Entities**: Stateful objects that persist across flows
- **Flows**: Business logic that generates event sequences
- **Context**: Flow state and entity selection
- **Outputs**: Multiple destinations for generated events

## Core Components

### Events

Events are Pydantic models that define your data schema with built-in fake data generation:

```python
class UserRegistered(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    email: str = Field(faker="email")
    registration_date: datetime = Field(faker="now")
    account_type: str = Field(
        faker="random_element",
        elements=["free", "premium", "enterprise"]
    )
```

**Key Features:**

- **Type Safety**: Full Pydantic validation and typing
- **Fake Data**: Automatic realistic data generation
- **Primary Keys**: Mark fields that identify entities
- **System Fields**: Automatic event ID, timestamp, session tracking

### Entities

Entities represent stateful objects in your simulation:

```python
class User(Entity):
    source_event = UserRegistered  # Event that creates this entity
    primary_key = "user_id"        # Links entity to event

    # State fields with defaults and types
    is_active: bool = StateField(default=True, type_=bool)
    login_count: int = StateField(default=0, type_=int)
    last_seen: datetime = StateField(default=None, type_=datetime)

    # Copy initial value from source event
    account_type: str = StateField(from_field="account_type", type_=str)
```

**State Management:**

- **Persistence**: State persists across flows and time
- **Versioning**: Full temporal state tracking
- **Mutations**: Explicit state updates through SetState actions

### Actions

Actions are declarative instructions that flows yield to the simulation engine:

| Action     | Purpose                    | Example                                           |
| ---------- | -------------------------- | ------------------------------------------------- |
| `NewEvent` | Generate an event          | `NewEvent(ctx, UserLogin, save_entity=User)`      |
| `AddDecay` | Advance time with drop-off | `AddDecay(ctx, rate=0.3, minutes=5)`              |
| `SetState` | Update entity state        | `SetState(User, [("login_count", "add", 1)])`     |
| `Select`   | Filter entities            | `Select(User, where=[("is_active", "is", True)])` |

### Flows

Flows define business logic as Python generators:

```python
@sim.flow(
    initiation_weight=8.0,  # Relative probability of starting
    filter=Select(User, where=[("is_active", "is", True)])  # Prerequisites
)
def user_session_flow(ctx: FlowContext):
    """Active users log in and browse."""
    # Get the selected user
    user = ctx.get_entity(User)

    # Generate login event with state mutation
    yield NewEvent(
        ctx, UserLogin,
        mutate=SetState(User, [("login_count", "add", 1)])
    )

    # 30% chance to drop off after 2 minutes
    yield AddDecay(ctx, rate=0.3, minutes=2)

    # Continue with browsing...
    yield NewEvent(ctx, PageView, page="/dashboard")
```

### Simulation

The simulation orchestrates everything:

```python
sim = Simulation(
    duration="30m",          # How long to simulate
    start_time="now",        # When to start
    time_step="1s",          # Time resolution
    n_flows=5,               # Concurrent flows
    random_seed=42,          # Reproducible results
    initial_entities={       # Pre-existing entities
        User: 100,
        Product: 20
    }
)
```

## Key Concepts

### Context and State

The simulation maintains two levels of context:

**Global Context:**

- Manages all entities and their states over time
- Tracks which entities are available vs. active in flows
- Provides global simulation clock

**Flow Context:**

- Maintains session ID for event correlation
- Tracks selected entities for the current flow
- Has its own clock that advances with AddDecay

### Entity Management

Entities are managed with full temporal tracking:

```python
# Entity states are versioned over time
(User, id:123, state:logged_out, valid_from:'10:00:00', valid_to:'10:05:30')
(User, id:123, state:logged_in,  valid_from:'10:05:30', valid_to:None)

# Query entities at specific times
available_users = entity_manager.query(
    User,
    where=[("is_active", "is", True)],
    time='10:03:00'
)
```

### Implicit State and Mutations

The system automatically manages some state:

**Implicit State Fields:**

- `flow_name`: Tracks which flow currently owns an entity
- Available entities have `flow_name = None`
- Active entities have `flow_name = "flow_12345"`

**Implicit Filtering:**

- All flows automatically filter for `flow_name = None`
- Prevents double-booking of entities

**Implicit Mutations:**

- Entity `flow_name` is set when entering a flow
- Entity `flow_name` is cleared when exiting a flow

### Entity Selection and Filtering

Flows can specify prerequisites for starting:

```python
@sim.flow(
    initiation_weight=5.0,
    filter=Select(User, where=[
        ("is_active", "is", True),
        ("login_count", "greater_than", 5)
    ])
)
def power_user_flow(ctx: FlowContext):
    # This flow only runs if we can find an active user
    # with more than 5 logins who isn't already in a flow
    pass
```

## Configuration Reference

### Supported Faker Types

| Faker            | Parameters                                   | Example Output                           |
| ---------------- | -------------------------------------------- | ---------------------------------------- |
| `uuid4`          | -                                            | `"f47ac10b-58cc-4372-a567-0e02b2c3d479"` |
| `shortuuid`      | `length=8`                                   | `"mBT5Q2Nx"`                             |
| `name`           | -                                            | `"John Smith"`                           |
| `email`          | -                                            | `"john@example.com"`                     |
| `random_element` | `elements=[...]`                             | Selected from list                       |
| `random_int`     | `min=1, max=100`                             | `42`                                     |
| `pyfloat`        | `min_value=0, max_value=1000, positive=True` | `123.45`                                 |
| `date_time`      | -                                            | `2025-01-15 14:30:00`                    |
| `now`            | -                                            | Current timestamp                        |
| `lexify`         | `text="PROD_????"`                           | `"PROD_A1B2"`                            |

### State Operations

| Operation    | Usage                          | Description                 |
| ------------ | ------------------------------ | --------------------------- |
| `"is"`       | `("status", "is", "active")`   | Set field to value          |
| `"add"`      | `("count", "add", 1)`          | Add to numeric field        |
| `"subtract"` | `("inventory", "subtract", 5)` | Subtract from numeric field |

### Filter Conditions

| Condition        | Usage                         | Description        |
| ---------------- | ----------------------------- | ------------------ |
| `"is"`           | `("status", "is", "active")`  | Exact match        |
| `"is_not"`       | `("cart_id", "is_not", None)` | Not equal          |
| `"greater_than"` | `("age", "greater_than", 18)` | Numeric comparison |
| `"less_than"`    | `("score", "less_than", 100)` | Numeric comparison |

### Output Types

| Output         | Purpose         | Configuration                          |
| -------------- | --------------- | -------------------------------------- |
| `StdOutOutput` | Console logging | `StdOutOutput()`                       |
| `FileOutput`   | JSON file       | `FileOutput("events.jsonl")`           |
| `KafkaOutput`  | Apache Kafka    | `KafkaOutput(topic_mapping={...})`     |
| `MySQLOutput`  | MySQL database  | `MySQLOutput(connection_config={...})` |

## Best Practices

1. **Start Simple**: Begin with basic flows and add complexity gradually
2. **Use Realistic Weights**: Model flow probabilities based on actual user behavior
3. **Plan State Carefully**: Design entity state fields before building flows
4. **Test Incrementally**: Run short simulations while developing
5. **Monitor Drop-offs**: Use AddDecay to model realistic user abandonment
6. **Correlate Events**: Use session IDs to trace user journeys
7. **Validate Output**: Always verify generated events match expectations

## Example Use Cases

- **E-commerce**: User registration, product browsing, cart abandonment, purchases
- **SaaS Applications**: User onboarding, feature usage, subscription management
- **IoT Systems**: Device telemetry, status updates, alert generation
- **Financial Services**: Account creation, transactions, risk events
- **Gaming**: Player actions, progression, in-game purchases
- **Marketing**: Campaign interactions, lead scoring, conversion funnels

Deep Faker enables you to create sophisticated, realistic event simulations with minimal code while maintaining full control over timing, state, and business logic.
