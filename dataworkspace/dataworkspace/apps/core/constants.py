from django.db import models


class PostgresDataTypes(models.TextChoices):
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    NUMERIC = "numeric"
    TEXT = "text"
    UUID = "uuid"


SCHEMA_POSTGRES_DATA_TYPE_MAP = {
    "integer": PostgresDataTypes.INTEGER,
    "boolean": PostgresDataTypes.BOOLEAN,
    "date": PostgresDataTypes.DATE,
    "datetime": PostgresDataTypes.TIMESTAMP,
    "numeric": PostgresDataTypes.NUMERIC,
    "text": PostgresDataTypes.TEXT,
    "uuid": PostgresDataTypes.UUID,
}
TABLESCHEMA_FIELD_TYPE_MAP = {
    "number": "numeric",
}
