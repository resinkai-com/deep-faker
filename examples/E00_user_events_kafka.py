from datetime import datetime

from deep_faker import (
    AddDecay,
    BaseEvent,
    Entity,
    Field,
    FileOutput,
    FlowContext,
    NewEvent,
    Select,
    SetState,
    Simulation,
    StateField,
    StdOutOutput,
)
from deep_faker.outputs import KafkaOutput


# Define Event Schemas matching Kafka DDL
class UserRegistered(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    email: str = Field(faker="email")
    event_time: datetime = Field(faker="now")


class UserEmailChanged(BaseEvent):
    user_id: str
    original_email: str
    email: str = Field(faker="email")
    event_time: datetime = Field(faker="now")


# Define User Entity with email state tracking
class User(Entity):
    source_event = UserRegistered
    primary_key = "user_id"

    # State fields
    email: str = StateField(from_field="email", type_=str)
    registration_time: datetime = StateField(from_field="event_time", type_=datetime)
    email_change_count: int = StateField(default=0, type_=int)


# Create Simulation
sim = Simulation(
    duration="5m",
    start_time="now",
    n_flows=2,
    initial_entities={User: 0},  # Start with no existing users
)


# Flow 1: User Registration
@sim.flow(initiation_weight=3.0)
def user_registration_flow(ctx: FlowContext):
    """New users register to the platform."""
    yield NewEvent(ctx, UserRegistered, save_entity=User)

    # Small chance users immediately change their email after registration
    yield AddDecay(ctx, rate=0.8, seconds=30)  # 80% drop-off, 20% continue

    # Some users change their email right after registration
    user = ctx.get_selected_entity(User)
    original_email = user.email

    yield NewEvent(
        ctx,
        UserEmailChanged,
        original_email=original_email,
        mutate=SetState(User, [("email_change_count", "add", 1)]),
    )


# Flow 2: Existing User Email Change
@sim.flow(
    initiation_weight=1.0,
    filter=Select(User, where=[("email_change_count", "less_than", 3)]),
)
def email_change_flow(ctx: FlowContext):
    """Existing users change their email addresses."""
    user = ctx.get_selected_entity(User)
    original_email = user.email

    yield NewEvent(
        ctx,
        UserEmailChanged,
        original_email=original_email,
        mutate=SetState(User, [("email_change_count", "add", 1)]),
    )


# Configure Outputs
sim.add_output(StdOutOutput())
sim.add_output(FileOutput("output/E00_user_events_kafka.jsonl"))

# For Kafka output (uncomment when Kafka is available)


sim.add_output(
    KafkaOutput(
        {
            UserRegistered: "e00-user-registered",
            UserEmailChanged: "e00-user-email-changed",
        },
        bootstrap_servers="localhost:9092",
    )
)

if __name__ == "__main__":
    sim.run()
