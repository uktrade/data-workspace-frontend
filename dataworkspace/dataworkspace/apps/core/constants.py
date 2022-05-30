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

DATA_FLOW_TASK_ERROR_MAP = {
    r".*Unable to decode CSV as.*|.*UnicodeDecodeError.*": "core/partial/errors/decode.html",
    r".*invalid input syntax for (type )?(numeric|integer).*": "core/partial/errors/input-syntax.html",
    r".*NumericValueOutOfRange.*": "core/partial/errors/out-of-range.html",
    r".*DatetimeFieldOverflow.*|.*InvalidDatetimeFormat*": "core/partial/errors/invalid-date.html",
}
