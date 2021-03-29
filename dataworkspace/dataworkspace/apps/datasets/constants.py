from django.db import models


LINKED_FIELD_IDENTIFIER = 'IDENTIFIER'
LINKED_FIELD_DISPLAY_NAME = 'DISPLAY_NAME'


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
