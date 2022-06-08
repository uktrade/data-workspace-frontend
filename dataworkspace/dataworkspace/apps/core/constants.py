from django.db import models


class PostgresDataTypes(models.TextChoices):
    BIGINT = "bigint"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    NUMERIC = "numeric"
    TEXT = "text"
    UUID = "uuid"


SCHEMA_POSTGRES_DATA_TYPE_MAP = {
    "Integer": PostgresDataTypes.BIGINT,
    "Boolean": PostgresDataTypes.BOOLEAN,
    "Date": PostgresDataTypes.DATE,
    "Date time": PostgresDataTypes.TIMESTAMP,
    "Numeric": PostgresDataTypes.NUMERIC,
    "Text": PostgresDataTypes.TEXT,
    "UUID": PostgresDataTypes.UUID,
}
TABLESCHEMA_FIELD_TYPE_MAP = {
    "number": "numeric",
}
