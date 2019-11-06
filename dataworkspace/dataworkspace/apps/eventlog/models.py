from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class EventLog(models.Model):
    TYPE_DATASET_SOURCE_LINK_DOWNLOAD = 1
    TYPE_DATASET_SOURCE_TABLE_DOWNLOAD = 2
    TYPE_REFERENCE_DATASET_DOWNLOAD = 3
    TYPE_DATASET_TABLE_DATA_DOWNLOAD = 4
    TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD = 5
    TYPE_DATASET_SOURCE_VIEW_DOWNLOAD = 6
    _TYPE_CHOICES = (
        (TYPE_DATASET_SOURCE_LINK_DOWNLOAD, 'Dataset source link download'),
        (TYPE_DATASET_SOURCE_TABLE_DOWNLOAD, 'Dataset source table download'),
        (TYPE_REFERENCE_DATASET_DOWNLOAD, 'Reference dataset download'),
        (TYPE_DATASET_TABLE_DATA_DOWNLOAD, 'Table data download'),
        (TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD, 'SQL query download'),
        (TYPE_DATASET_SOURCE_VIEW_DOWNLOAD, 'Dataset source view download'),
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.DO_NOTHING, related_name='events'
    )
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    event_type = models.IntegerField(choices=_TYPE_CHOICES)
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=255, null=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    extra = JSONField(null=True, encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ('-timestamp',)
        get_latest_by = 'timestamp'

    def __str__(self):
        return '{} – {} – {}'.format(
            self.timestamp,
            self.user.get_full_name(),  # pylint: disable=no-member
            self.get_event_type_display(),
        )
