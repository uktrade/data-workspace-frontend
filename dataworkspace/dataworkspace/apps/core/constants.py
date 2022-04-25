from dataworkspace.apps.your_files.constants import PostgresDataTypes

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
