"""Core base classes and fields for deep_faker."""

import uuid
from datetime import datetime
from typing import Any, List, Optional, Type

import pydantic
from faker import Faker


def Field(
    *,
    faker: str = None,
    primary_key: bool = False,
    elements: Optional[List] = None,
    **kwargs,
):
    """Custom field that accepts generator hints."""
    # Extract faker-specific parameters that should go in json_schema_extra
    faker_params = {}
    pydantic_params = {}

    # Parameters that should go in json_schema_extra for faker
    faker_keys = {"positive", "min_value", "max_value", "min", "max", "text"}

    for key, value in kwargs.items():
        if key in faker_keys:
            faker_params[key] = value
        else:
            pydantic_params[key] = value

    # Use pydantic's json_schema_extra to store our metadata
    extra = pydantic_params.get("json_schema_extra", {})
    extra.update(
        {
            "faker": faker,
            "primary_key": primary_key,
            "elements": elements,
            **faker_params,  # Include faker-specific parameters
        }
    )
    pydantic_params["json_schema_extra"] = extra

    return pydantic.Field(**pydantic_params)


class BaseEvent(pydantic.BaseModel):
    """Base class for all events."""

    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True, use_enum_values=True
    )

    # Standard event metadata fields
    sys__eid: str = Field(faker="uuid4")  # Unique ID for each event
    sys__ets: int = Field(
        default=0
    )  # Event timestamp in milliseconds (set by simulation)
    sys__sid: str = Field(default="")  # Session ID for the flow (set by simulation)


class StateField:
    """Descriptor for a managed state attribute on an Entity."""

    def __init__(self, default=None, from_field: str = None, type_=None):
        self.default = default
        self.from_field = from_field
        self.type = type_
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj._state.get(self.name, self.default)

    def __set__(self, obj, value):
        obj._state[self.name] = value


class EntityMeta(type):
    """Metaclass for Entity to handle registration and setup."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace)

        # Store state fields
        cls._state_fields = {}
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, StateField):
                cls._state_fields[attr_name] = attr_value

        return cls


class Entity(metaclass=EntityMeta):
    """Base class for all stateful entities."""

    source_event: Type[BaseEvent] = None
    primary_key: str = None

    def __init__(self, **kwargs):
        self._state = {}
        self._primary_key_value = None

        # Initialize state fields with defaults
        for field_name, field in self._state_fields.items():
            if field.from_field and field.from_field in kwargs:
                self._state[field_name] = kwargs[field.from_field]
            else:
                self._state[field_name] = field.default

        # Set primary key if provided
        if self.primary_key and self.primary_key in kwargs:
            self._primary_key_value = kwargs[self.primary_key]

    def get_primary_key(self):
        return self._primary_key_value

    def update_state(self, updates: List[tuple]):
        """Update entity state with list of (field, operation, value) tuples."""
        for field, operation, value in updates:
            if operation == "is":
                setattr(self, field, value)
            elif operation == "add":
                current = getattr(self, field, 0)
                setattr(self, field, current + value)
            elif operation == "subtract":
                current = getattr(self, field, 0)
                setattr(self, field, current - value)


def generate_fake_data(
    field_info: pydantic.fields.FieldInfo,
    faker_instance: Faker,
    current_time: Optional[datetime] = None,
) -> Any:
    """Generate fake data based on field configuration."""
    # Extract faker metadata from json_schema_extra
    extra = getattr(field_info, "json_schema_extra", {})
    if not extra:
        return None

    faker_type = extra.get("faker")
    elements = extra.get("elements")

    if not faker_type:
        return None

    if faker_type == "uuid4":
        return str(uuid.uuid4())
    elif faker_type == "now":
        return current_time if current_time is not None else datetime.now()
    elif faker_type == "name":
        return faker_instance.name()
    elif faker_type == "email":
        return faker_instance.email()
    elif faker_type == "date_time_this_decade":
        return faker_instance.date_time_this_decade()
    elif faker_type == "date_time":
        return faker_instance.date_time()
    elif faker_type == "ean":
        return faker_instance.ean()
    elif faker_type == "catch_phrase":
        return faker_instance.catch_phrase()
    elif faker_type == "user_name":
        return faker_instance.user_name()
    elif faker_type == "company":
        return faker_instance.company()
    elif faker_type == "lexify":
        text = extra.get("text", "????")
        return faker_instance.lexify(text=text)
    elif faker_type == "pyfloat":
        min_value = extra.get("min_value", 0)
        max_value = extra.get("max_value", 1000)
        positive = extra.get("positive", False)

        # Handle the case where positive=True conflicts with min_value <= 0
        if positive and min_value <= 0:
            min_value = 0.001  # Set a small positive minimum

        return faker_instance.pyfloat(
            min_value=min_value, max_value=max_value, positive=positive
        )
    elif faker_type == "random_int":
        min_val = extra.get("min", 1)
        max_val = extra.get("max", 100)
        return faker_instance.random_int(min=min_val, max=max_val)
    elif faker_type == "random_element" and elements:
        return faker_instance.random_element(elements)
    elif hasattr(faker_instance, faker_type):
        faker_method = getattr(faker_instance, faker_type)
        if callable(faker_method):
            # Try to call with any additional parameters from extra
            try:
                method_kwargs = {
                    k: v
                    for k, v in extra.items()
                    if k not in ["faker", "primary_key", "elements"]
                }
                return faker_method(**method_kwargs)
            except TypeError:
                # If that fails, call without parameters
                return faker_method()

    return None
