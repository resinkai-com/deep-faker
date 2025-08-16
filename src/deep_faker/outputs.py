"""Output handlers for sending events to external systems."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Type

from .base import BaseEvent
from .logging import get_logger

try:
    from kafka import KafkaProducer

    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

try:
    import mysql.connector

    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class BaseOutput:
    """Base class for all output handlers."""

    def send_event(self, event: BaseEvent):
        """Send an event to the output destination."""
        raise NotImplementedError

    def close(self):
        """Close the output handler and clean up resources."""
        pass


class StdOutOutput(BaseOutput):
    """Output events to stdout."""

    def send_event(self, event: BaseEvent):
        """Send event to stdout as JSON."""
        event_dict = event.model_dump()
        event_dict["event_type"] = event.__class__.__name__
        print(json.dumps(event_dict, default=str))


class FileOutput(BaseOutput):
    """Output events to a file."""

    def __init__(self, file_path: str, format: str = "json"):
        self.file_path = Path(file_path)
        self.format = format
        self.file_handle = None
        self._open_file()

    def _open_file(self):
        """Open the output file for writing."""
        self.file_handle = open(self.file_path, "w")

    def send_event(self, event: BaseEvent):
        """Send event to file."""
        if not self.file_handle:
            return

        event_dict = event.model_dump()
        event_dict["event_type"] = event.__class__.__name__

        if self.format == "json":
            self.file_handle.write(json.dumps(event_dict, default=str) + "\n")
        else:
            self.file_handle.write(str(event_dict) + "\n")

        self.file_handle.flush()

    def close(self):
        """Close the file handle."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


class KafkaOutput(BaseOutput):
    """Output events to Kafka topics."""

    def __init__(
        self,
        topic_mapping: Dict[Type[BaseEvent], str],
        bootstrap_servers: str = "localhost:9092",
        **kwargs,
    ):
        if not KAFKA_AVAILABLE:
            raise ImportError("kafka-python is required for KafkaOutput")

        self.topic_mapping = topic_mapping
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x, default=str).encode("utf-8"),
            **kwargs,
        )

    def send_event(self, event: BaseEvent):
        """Send event to appropriate Kafka topic."""
        event_type = type(event)
        topic = self.topic_mapping.get(event_type)

        if topic:
            event_dict = event.model_dump()
            event_dict["event_type"] = event.__class__.__name__

            self.producer.send(topic, value=event_dict)

    def close(self):
        """Close the Kafka producer."""
        if hasattr(self, "producer"):
            self.producer.flush()
            self.producer.close()


class MySQLOutput(BaseOutput):
    """Output events to MySQL database."""

    def __init__(
        self,
        host: str = "localhost",
        user: str = "root",
        password: str = "",
        database: str = "events",
        table_mapping: Optional[Dict[Type[BaseEvent], str]] = None,
    ):
        if not MYSQL_AVAILABLE:
            raise ImportError("mysql-connector-python is required for MySQLOutput")

        self.connection_config = {
            "host": host,
            "user": user,
            "password": password,
            "database": database,
        }
        self.table_mapping = table_mapping or {}
        self.connection = None
        self.cursor = None
        self.logger = get_logger(__name__)
        self._connect()

    def _connect(self):
        """Connect to MySQL database."""
        try:
            self.connection = mysql.connector.connect(**self.connection_config)
            self.cursor = self.connection.cursor()
        except mysql.connector.Error as e:
            self.logger.error(f"Error connecting to MySQL: {e}")

    def _get_table_name(self, event_type: Type[BaseEvent]) -> str:
        """Get table name for event type."""
        return self.table_mapping.get(event_type, event_type.__name__.lower())

    def _ensure_table_exists(self, table_name: str, event_dict: Dict[str, Any]):
        """Create table if it doesn't exist."""
        if not self.cursor:
            return

        # Simple table creation - in production this would be more sophisticated
        columns = []
        for key, value in event_dict.items():
            if isinstance(value, str):
                columns.append(f"{key} TEXT")
            elif isinstance(value, int):
                columns.append(f"{key} INT")
            elif isinstance(value, float):
                columns.append(f"{key} FLOAT")
            else:
                columns.append(f"{key} TEXT")

        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            {', '.join(columns)}
        )
        """

        try:
            self.cursor.execute(create_sql)
            self.connection.commit()
        except mysql.connector.Error as e:
            self.logger.error(f"Error creating table {table_name}: {e}")

    def send_event(self, event: BaseEvent):
        """Send event to MySQL table."""
        if not self.cursor or not self.connection:
            return

        event_dict = event.model_dump()
        event_dict["event_type"] = event.__class__.__name__

        table_name = self._get_table_name(type(event))
        self._ensure_table_exists(table_name, event_dict)

        # Convert values to strings for simplicity
        str_dict = {k: str(v) for k, v in event_dict.items()}

        columns = ", ".join(str_dict.keys())
        placeholders = ", ".join(["%s"] * len(str_dict))
        values = list(str_dict.values())

        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        try:
            self.cursor.execute(insert_sql, values)
            self.connection.commit()
        except mysql.connector.Error as e:
            self.logger.error(f"Error inserting into {table_name}: {e}")

    def close(self):
        """Close MySQL connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
