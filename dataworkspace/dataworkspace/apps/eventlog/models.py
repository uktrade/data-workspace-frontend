from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class EventLog(models.Model):
    TYPE_DATASET_SOURCE_LINK_DOWNLOAD = 1
    TYPE_DATASET_SOURCE_TABLE_DOWNLOAD = 2
    TYPE_REFERENCE_DATASET_DOWNLOAD = 3
    TYPE_DATASET_TABLE_DATA_DOWNLOAD = 4
    TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD = 5
    TYPE_DATASET_SOURCE_VIEW_DOWNLOAD = 6
    TYPE_VISUALISATION_APPROVED = 7
    TYPE_VISUALISATION_UNAPPROVED = 8
    TYPE_DATASET_ACCESS_REQUEST = 9
    TYPE_GRANTED_DATASET_PERMISSION = 10
    TYPE_REVOKED_DATASET_PERMISSION = 11
    TYPE_GRANTED_USER_PERMISSION = 12
    TYPE_REVOKED_USER_PERMISSION = 13
    TYPE_GRANTED_VISUALISATION_PERMISSION = 14
    TYPE_REVOKED_VISUALISATION_PERMISSION = 15
    TYPE_SET_DATASET_USER_ACCESS_TYPE = 16
    TYPE_VIEW_QUICKSIGHT_VISUALISATION = 17
    TYPE_DATA_EXPLORER_SAVED_QUERY = 19
    TYPE_VIEW_SUPERSET_VISUALISATION = 20
    TYPE_VIEW_VISUALISATION_TEMPLATE = 21
    TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE = 22
    TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN = 23
    TYPE_TOOLS_ACCESS_REQUEST = 24
    TYPE_DATASET_NOTIFICATIONS_SUBSCRIBED = 25
    TYPE_DATASET_NOTIFICATIONS_UNSUBSCRIBED = 26
    TYPE_REFERENCE_DATASET_VIEW = 27
    TYPE_DATASET_VIEW = 28
    TYPE_DATASET_FIND_FORM_QUERY = 29
    TYPE_REMOVE_DATASET_FROM_COLLECTION = 30
    TYPE_REMOVE_VISUALISATION_FROM_COLLECTION = 30
    TYPE_ADD_DATASET_TO_COLLECTION = 31

    _TYPE_CHOICES = (
        (TYPE_DATASET_SOURCE_LINK_DOWNLOAD, "Dataset source link download"),
        (TYPE_DATASET_SOURCE_TABLE_DOWNLOAD, "Dataset source table download"),
        (TYPE_REFERENCE_DATASET_DOWNLOAD, "Reference dataset download"),
        (TYPE_DATASET_TABLE_DATA_DOWNLOAD, "Table data download"),
        (TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD, "SQL query download"),
        (TYPE_DATASET_SOURCE_VIEW_DOWNLOAD, "Dataset source view download"),
        (TYPE_VISUALISATION_APPROVED, "Visualisation approved"),
        (TYPE_VISUALISATION_UNAPPROVED, "Visualisation unapproved"),
        (TYPE_DATASET_ACCESS_REQUEST, "Dataset access request"),
        (TYPE_GRANTED_DATASET_PERMISSION, "Granted dataset permission"),
        (TYPE_REVOKED_DATASET_PERMISSION, "Revoked dataset permission"),
        (TYPE_GRANTED_USER_PERMISSION, "Granted user permission"),
        (TYPE_REVOKED_USER_PERMISSION, "Revoked user permission"),
        (TYPE_GRANTED_VISUALISATION_PERMISSION, "Granted visualisation permission"),
        (TYPE_REVOKED_VISUALISATION_PERMISSION, "Revoked visualisation permission"),
        (TYPE_SET_DATASET_USER_ACCESS_TYPE, "Set dataset user access type"),
        (TYPE_VIEW_QUICKSIGHT_VISUALISATION, "View AWS QuickSight visualisation"),
        (TYPE_DATA_EXPLORER_SAVED_QUERY, "Saved a query in Data Explorer"),
        (TYPE_VIEW_SUPERSET_VISUALISATION, "View Superset visualisation"),
        (TYPE_VIEW_VISUALISATION_TEMPLATE, "View visualisation"),
        (TYPE_DATASET_CUSTOM_QUERY_DOWNLOAD_COMPLETE, "SQL query download complete"),
        (
            TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
            "Changed dataset authorized email domains",
        ),
        (TYPE_TOOLS_ACCESS_REQUEST, "Tools access request"),
        (TYPE_DATASET_NOTIFICATIONS_SUBSCRIBED, "Subscribed to dataset notification"),
        (TYPE_DATASET_NOTIFICATIONS_UNSUBSCRIBED, "Unsubscribed from dataset notification"),
        (TYPE_REFERENCE_DATASET_VIEW, "Reference dataset view"),
        (TYPE_DATASET_VIEW, "Dataset view"),
        (TYPE_DATASET_FIND_FORM_QUERY, "Dataset find form query"),
        (TYPE_REMOVE_DATASET_FROM_COLLECTION, "Remove dataset from collection"),
        (TYPE_ADD_DATASET_TO_COLLECTION, "Add dataset to collection"),
    )
    user = models.ForeignKey(get_user_model(), on_delete=models.DO_NOTHING, related_name="events")
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    event_type = models.IntegerField(choices=_TYPE_CHOICES)
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=255, null=True)
    related_object = GenericForeignKey("content_type", "object_id")
    extra = models.JSONField(null=True, encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ("-timestamp",)
        get_latest_by = "timestamp"

    def __str__(self):
        return "{} – {} – {}".format(
            self.timestamp,
            self.user.get_full_name(),  # pylint: disable=no-member
            self.get_event_type_display(),
        )
