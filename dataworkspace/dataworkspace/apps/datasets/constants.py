from django.db import models


LINKED_FIELD_IDENTIFIER = 'IDENTIFIER'
LINKED_FIELD_DISPLAY_NAME = 'DISPLAY_NAME'

# Map some postgres data types to types ag-grid can filter against.
# If not set falls back to `text` on the frontend
GRID_DATA_TYPE_MAP = {
    'smallint': 'numeric',
    'integer': 'numeric',
    'bigint': 'numeric',
    'decimal': 'numeric',
    'numeric': 'numeric',
    'real': 'numeric',
    'timestamp': 'date',
    'timestamp with time zone': 'date',
    'timestamp without time zone': 'date',
    'date': 'date',
}


class DataSetType(models.IntegerChoices):
    # Used to define what kind of data set we're dealing with.
    # These values are persisted to the database - do not change them.
    REFERENCE = 0, 'Reference Dataset'
    MASTER = 1, 'Master Dataset'
    DATACUT = 2, 'Data Cut'
    VISUALISATION = 3, 'Visualisation'


class DataLinkType(models.IntegerChoices):
    SOURCE_LINK = 0
    SOURCE_TABLE = 1
    SOURCE_VIEW = 2
    CUSTOM_QUERY = 3


class TagType(models.IntegerChoices):
    SOURCE = 1, 'Source'
    TOPIC = 2, 'Topic'
