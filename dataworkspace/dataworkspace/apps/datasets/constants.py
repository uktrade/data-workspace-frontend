import enum

LINKED_FIELD_IDENTIFIER = 'IDENTIFIER'
LINKED_FIELD_DISPLAY_NAME = 'DISPLAY_NAME'


class DataSetType(enum.Enum):
    # Used to define what kind of data set we're dealing with.
    # These values are persisted to the database - do not change them.
    REFERENCE = 0
    MASTER = 1
    DATACUT = 2
    VISUALISATION = 3


class DataLinkType(enum.Enum):
    SOURCE_LINK = 0
    SOURCE_TABLE = 1
    SOURCE_VIEW = 2
    CUSTOM_QUERY = 3


class TagType(enum.Enum):
    SOURCE = 1
    TOPIC = 2
