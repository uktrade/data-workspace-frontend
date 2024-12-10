from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from dataworkspace.apps.eventlog.constants import SystemStatLogEventType


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
    TYPE_REMOVE_VISUALISATION_FROM_COLLECTION = 31
    TYPE_ADD_DATASET_TO_COLLECTION = 32
    TYPE_ADD_VISUALISATION_TO_COLLECTION = 33
    TYPE_ADD_USER_TO_COLLECTION = 34
    TYPE_REMOVE_USER_FROM_COLLECTION = 35
    TYPE_EDITED_COLLECTION = 36
    TYPE_CREATED_COLLECTION = 37
    TYPE_EDITED_COLLECTION_NOTES = 38
    TYPE_COLLECTION_VIEW = 39
    TYPE_GRANTED_VISUALISATION_ADMIN_PERMISSION = 40
    TYPE_REVOKED_VISUALISATION_ADMIN_PERMISSION = 41
    TYPE_DATA_TABLE_VIEW = 42
    TYPE_DATA_PREVIEW_TIMEOUT = 43
    TYPE_DATA_PREVIEW_COMPLETE = 44
    TYPE_DATA_TABLE_VIEW_SAVED = 45
    TYPE_USER_TOOL_ECS_STARTED = 46
    TYPE_USER_TOOL_STOPPED = 47
    TYPE_USER_TOOL_LINK_STARTED = 48
    TYPE_DATA_CATALOGUE_EDITOR_ADDED = 49
    TYPE_DATA_CATALOGUE_EDITOR_REMOVED = 50
    TYPE_DATASET_BOOKMARKED = 51
    TYPE_DATASET_UNBOOKMARKED = 52
    TYPE_USER_TOOL_FAILED = 53
    TYPE_USER_DATACUT_GRID_VIEW_FAILED = 54
    TYPE_DATASET_NOTIFICATION_SENT_TO_USER = 55
    TYPE_STATA_ACCESS_REQUEST = 56
    TYPE_ADD_TABLE_TO_SOURCE_DATASET = 57
    TYPE_CHANGED_DATASET_DESCRIPTION = 58

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
        (TYPE_REMOVE_VISUALISATION_FROM_COLLECTION, "Remove visualisation from collection"),
        (TYPE_ADD_DATASET_TO_COLLECTION, "Add dataset to collection"),
        (TYPE_ADD_VISUALISATION_TO_COLLECTION, "Add visualisation to collection"),
        (TYPE_ADD_USER_TO_COLLECTION, "Add user to collection"),
        (TYPE_REMOVE_USER_FROM_COLLECTION, "Remove user from collection"),
        (TYPE_EDITED_COLLECTION, "Edited collection"),
        (TYPE_CREATED_COLLECTION, "Created collection"),
        (TYPE_EDITED_COLLECTION_NOTES, "Edited collection notes"),
        (TYPE_COLLECTION_VIEW, "Collection view"),
        (TYPE_GRANTED_VISUALISATION_ADMIN_PERMISSION, "Granted visualisation admin permission"),
        (TYPE_REVOKED_VISUALISATION_ADMIN_PERMISSION, "Revoked visualisation admin permission"),
        (TYPE_DATA_TABLE_VIEW, "Data table view"),
        (TYPE_DATA_PREVIEW_TIMEOUT, "Data table view load timeout"),
        (TYPE_DATA_PREVIEW_COMPLETE, "Data table view load complete"),
        (TYPE_DATA_TABLE_VIEW_SAVED, "Data table view saved"),
        (TYPE_USER_TOOL_ECS_STARTED, "Tool started (ECS)"),
        (TYPE_USER_TOOL_STOPPED, "Tool stopped by user"),
        (TYPE_USER_TOOL_LINK_STARTED, "Tool started (Link)"),
        (TYPE_DATA_CATALOGUE_EDITOR_ADDED, "Data Catalogue Editor user added"),
        (TYPE_DATA_CATALOGUE_EDITOR_REMOVED, "Data Catalogue Editor user removed"),
        (TYPE_DATASET_BOOKMARKED, "Dataset bookmarked"),
        (TYPE_DATASET_UNBOOKMARKED, "Dataset bookmark removed"),
        (TYPE_USER_TOOL_FAILED, "Tool failed to start for user"),
        (TYPE_USER_DATACUT_GRID_VIEW_FAILED, "Datacut grid failed to load for user"),
        (TYPE_DATASET_NOTIFICATION_SENT_TO_USER, "Dataset nofitication sent to user"),
        (TYPE_STATA_ACCESS_REQUEST, "Stata access request"),
        (TYPE_ADD_TABLE_TO_SOURCE_DATASET, "Added table to source dataset"),
        (TYPE_CHANGED_DATASET_DESCRIPTION, "Dataset description has changed"),
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


class SystemEventLogManager(models.Manager):
    def log_permissions_query_runtime(self, runtime, extra=None):
        return SystemStatLog.objects.create(
            type=SystemStatLogEventType.PERMISSIONS_QUERY_RUNTIME, stat=runtime, extra=extra
        )


class SystemStatLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    type = models.IntegerField(choices=SystemStatLogEventType.choices)
    stat = models.FloatField(null=True)
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=255, null=True)
    related_object = GenericForeignKey("content_type", "object_id")
    extra = models.JSONField(null=True, encoder=DjangoJSONEncoder)

    objects = SystemEventLogManager()

    class Meta:
        ordering = ("-timestamp",)
        get_latest_by = "timestamp"
        verbose_name_plural = "System stats"
