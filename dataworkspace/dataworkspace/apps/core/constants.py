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
    "integer": PostgresDataTypes.BIGINT,
    "boolean": PostgresDataTypes.BOOLEAN,
    "date": PostgresDataTypes.DATE,
    "datetime": PostgresDataTypes.TIMESTAMP,
    "numeric": PostgresDataTypes.NUMERIC,
    "text": PostgresDataTypes.TEXT,
    "UUID": PostgresDataTypes.UUID,
}
TABLESCHEMA_FIELD_TYPE_MAP = {
    "number": "numeric",
}

DATA_FLOW_TASK_ERROR_MAP = {
    r".*is of type bigint but expression is of type boolean.*": "core/partial/errors/setting-boolean-integer.html",
    r".*is of type numeric but expression is of type boolean.*": "core/partial/errors/setting-boolean-numeric.html",
    r".*is of type date but expression is of type boolean.*": "core/partial/errors/setting-boolean-date.html",
    r".*is of type timestamp with time zone but expression is of type boolean.*": "core/partial/errors/setting-boolean-datetime.html",  # pylint: disable=line-too-long
    r".*Not a boolean value*.": "core/partial/errors/setting-value-as-boolean.html",
    r".*invalid input syntax for type bigint.*": "core/partial/errors/setting-string-integer.html",
    r".*invalid input syntax for type numeric.*": "core/partial/errors/setting-string-numeric.html",
    r".*is of type date.*|.*invalid input syntax for type date*.": "core/partial/errors/setting-value-as-date.html",
    r".*is of type timestamp.*|.*invalid input syntax for type timestamp*.": "core/partial/errors/setting-value-as-datetime.html",  # pylint: disable=line-too-long
    r".*date/time field value out of range.*": "core/partial/errors/setting-date-as-incorrect-date.html",
}
