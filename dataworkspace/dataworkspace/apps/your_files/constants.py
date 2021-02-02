import enum


class PostgresDataTypes(enum.Enum):
    INTEGER = 'integer'
    BOOLEAN = 'boolean'
    DATE = 'date'
    TIMESTAMP = 'timestamp'
    NUMERIC = 'numeric'
    TEXT = 'text'
