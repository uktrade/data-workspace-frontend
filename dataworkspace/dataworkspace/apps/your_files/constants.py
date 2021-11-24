from django.db import models


class PostgresDataTypes(models.TextChoices):
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    NUMERIC = "numeric"
    TEXT = "text"
    UUID = "uuid"
