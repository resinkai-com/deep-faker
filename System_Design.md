# System Design: Python-Native Event Mocking (Declarative)

## 1. System Architecture

The architecture is centered around a Generator Engine that interprets declarative actions yielded by user-defined flows to manipulate a global state of entities.

- Configuration File (events_main.py): The user's script defining all schemas, entities, flows, and outputs.
- Simulation Object: The central controller. It's configured with simulation parameters, initial entity states, and a registry of flows and outputs. It orchestrates the entire run.
- Generator Engine: The heart of the system. It's a loop that:
  - Selects a flow to run based on its weight and entry conditions (filter).
  - Executes the flow, which yields a stream of Action objects.
  - Processes each Action (e.g., creating an event, updating entity state, advancing the clock).
  - Dispatches the generated events to all registered Outputs.
- Pydantic Schemas & Custom Field: Type-safe event models with built-in data generation logic.
- Entities & State Fields: Classes that explicitly define the stateful objects in the simulation (User, Product) and their managed attributes.
- Flows: Python generators that yield a sequence of Actions, defining a potential path through the state machine.
- Actions: Simple, declarative objects that represent a single operation to be performed by the engine (e.g., NewEvent, AddDecay, SetState).
- Outputs: Classes that send generated event data to external systems.

## 2. Core Component API Design

### 2.1. Pydantic Schemas & Generator-Aware Field

Event schemas are Pydantic models. We introduce a custom Field that accepts generator hints directly, simplifying the model definitions.

```python
import uuid
from datetime import datetime
import pydantic

# The library would provide these base classes and fields
class BaseEvent(pydantic.BaseModel):
    # Common logic, e.g., event timestamping, can go here
    pass

class Field(pydantic.Field):
    def __init__(self, *, faker: str = None, primary_key: bool = False, **kwargs):
        self.faker = faker
        self.primary_key = primary_key
        super().__init__(**kwargs)

# User-defined schemas
class UserRegistered(BaseEvent):
    user_id: uuid.UUID = Field(primary_key=True, faker="uuid4")
    full_name: str = Field(faker="name")
    email: str = Field(faker="email")
    registered_at: datetime = Field(faker="date_time_this_decade")

class ProductCreated(BaseEvent):
    product_id: str = Field(primary_key=True, faker="ean")
    name: str = Field(faker="ecommerce.product_name")
    status: str = Field(faker="random_element", elements=("available", "discontinued"))
```

### 2.2. Entity State Management

Entities are explicit classes that define the stateful objects of the simulation. StateField is a descriptor used to define attributes that are managed by the simulation engine.

```python
# The library would provide these base classes
class Entity:
    """Base class for all stateful entities."""
    # Metaclass logic handles registration and linking to source events
    pass

class StateField:
    """Descriptor for a managed state attribute on an Entity."""
    def __init__(self, default=None, from_field: str = None, type_=None):
        self.default = default
        self.from_field = from_field # Pulls initial value from a field in the source event
        self.type = type_

# User-defined entities
class User(Entity):
    source_event = UserRegistered  # This event creates a User
    primary_key = "user_id"        # Links the entity to the event payload

    # Managed state attributes
    is_logged_in: bool = StateField(default=False, type_=bool)
    last_login: datetime | None = StateField(default=None, type_=datetime)
    total_purchases: int = StateField(default=0, type_=int)

class Product(Entity):
    source_event = ProductCreated
    primary_key = "product_id"

    # The initial value for 'current_status' is copied from the 'status'
    # field of the ProductCreated event that created this entity.
    current_status: str = StateField(from_field="status", type_=str)
    inventory: int = StateField(default=100, type_=int)
```

### 2.3. Declarative Flows & Actions

Flows are standard Python functions that act as generators, yielding Action objects. This creates a declarative sequence of instructions for the engine to execute.

```python
# The library provides Action classes
class NewEvent:
    def __init__(self, ctx, event_schema, save_entity=None, mutate=None): ...

class AddDecay:
    def __init__(self, ctx, rate: float, **kwargs_for_time_delta): ...

class Select:
    def __init__(self, entity_type, where: list = None): ...

class SetState:
    def __init__(self, entity_type, updates: list[tuple]): ...

# --- User-defined flows ---
# The Simulation object is the central registry
sim = Simulation(
    duration="1h",
    initial_entities={User: 100, Product: 50},
    random_seed=42
)

@sim.flow(initiation_weight=5.0)
def new_user_onboarding(ctx: deep_faker.Context):
    """A new user registers, logs in, and might browse."""
    # Action 1: Create a UserRegistered event. The engine sees `save_entity=User`
    # and creates a new User entity in its state manager.
    yield NewEvent(ctx, UserRegistered, save_entity=User)

    # Action 2: Advance simulation time by 1 to 10 minutes.
    # There's a 20% chance the flow stops here.
    yield AddDecay(ctx, rate=0.2, minutes=faker.random_int(1, 10))

    # Action 3: Create a UserLoggedIn event. The `mutate` instruction tells
    # the engine to find the User associated with this context and update its state.
    yield NewEvent(
        ctx,
        UserLoggedIn,
        mutate=SetState(User, [("is_logged_in", "is", True)])
    )

@sim.flow(
    initiation_weight=10.0,
    # This flow can only start if the engine can find a User
    # that is currently logged in.
    filter=Select(User, where=[("is_logged_in", "is", True)])
)
def returning_user_session(ctx: deep_faker.Context):
    """A returning, logged-in user browses products."""
    yield NewEvent(ctx, HomePageView)
    yield AddDecay(ctx, rate=0.5, seconds=30)
    yield NewEvent(ctx, ProductPageView)
```

### 2.4. Complete Example: events_main.py

This file shows how all the declarative components work together.

```python
# examples/mysas/events_main.py

import uuid
from datetime import datetime
from faker import Faker

# Assume 'deep_faker' is the name of our library and it provides these components
from deep_faker import (
    Simulation, Context, BaseEvent, Entity, Field, StateField,
    NewEvent, AddDecay, Select, SetState
)
from deep_faker.outputs import KafkaOutput, StdOutOutput

# --- 1. Initialize Faker & Simulation ---
faker = Faker()
sim = Simulation(
    duration="30m",
    start_time="now",
    random_seed=101,
    initial_entities={
        "User": 500,  # Initialize with 500 existing users
        "Product": 100 # and 100 products
    }
)

# --- 2. Define Event Schemas ---
class UserRegistered(BaseEvent):
    user_id: uuid.UUID = Field(primary_key=True, faker="uuid4")
    full_name: str = Field(faker="name")

class UserLoggedIn(BaseEvent):
    user_id: uuid.UUID
    login_time: datetime = Field(faker="date_time")

class ProductCreated(BaseEvent):
    product_id: str = Field(primary_key=True, faker="ean")
    name: str = Field(faker="ecommerce.product_name")
    status: str = Field(faker="random_element", elements=["available", "coming_soon"])

class PageViewed(BaseEvent):
    user_id: uuid.UUID
    page: str

# --- 3. Define Entities and their State ---
class User(Entity):
    source_event = UserRegistered
    primary_key = "user_id"
    is_logged_in: bool = StateField(default=False, type_=bool)

class Product(Entity):
    source_event = ProductCreated
    primary_key = "product_id"
    current_status: str = StateField(from_field="status", type_=str)

# --- 4. Define Flows using Declarative Actions ---
@sim.flow(initiation_weight=2.0)
def new_user_flow(ctx: Context):
    """A new user is created and logs in."""
    yield NewEvent(ctx, UserRegistered, save_entity=User)
    yield AddDecay(ctx, seconds=15, rate=0.1) # 10% chance to drop off
    yield NewEvent(ctx, UserLoggedIn, mutate=SetState(User, [("is_logged_in", "is", True)]))

@sim.flow(
    initiation_weight=8.0,
    filter=Select(User, where=[("is_logged_in", "is", False)])
)
def returning_user_login_flow(ctx: Context):
    """An existing, logged-out user logs in and views the homepage."""
    yield NewEvent(ctx, UserLoggedIn, mutate=SetState(User, [("is_logged_in", "is", True)]))
    yield AddDecay(ctx, seconds=5, rate=0.05)
    yield NewEvent(ctx, PageViewed, page="/home")

# --- 5. Configure Outputs ---
sim.add_output(
    KafkaOutput(
        topic_mapping={
            UserRegistered: "user_profiles",
            ProductCreated: "product_catalog",
            UserLoggedIn: "user_activity",
            PageViewed: "user_activity",
        }
    )
)
sim.add_output(StdOutOutput())

# --- 6. Run the Simulation ---
if __name__ == "__main__":
    sim.run()
```

## Implementation Requirements

1. The outputs should support, 'file', 'stdout', 'kafka' and 'mysql'
2. Write two end to end tests that shows the events can be correctly generated based on the configs.
   1. One example for E-commerce focused event simulation
   2. One example for Trading platform event simulation
3. Both end to end tests should be runnable with pytest and both should pass.
