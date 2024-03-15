from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
import uuid

from dataworkspace.apps.core.models import (
    DeletableTimestampedUserModel,
)


class GraphDataset(DeletableTimestampedUserModel):
    """
    Skeleton Version of GraphDataset model, Dataset equivalent for ArangoDB. 
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(blank=False, null=False, max_length=128)
    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_owned_graph_datasets",
        null=True,
        blank=True,
    )
    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_managed_graph_datasets",
        null=True,
        blank=True,
    )
    short_description = models.CharField(blank=False, null=False, max_length=256)

    class Meta:
        db_table = "app_graphdataset"
        app_label = "arangodb"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class GraphDataSetUserPermission(models.Model):
    """
    Skeleton Version of GraphDataSetUserPermission model, DataSetUserPermission equivalent for ArangoDB. 
    """
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    collection = models.ForeignKey(GraphDataset, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_graphdatasetuserpermission"
        unique_together = ("user", "collection")


class SourceGraphCollection(models.Model):
    """
    Skeleton Version of SourceGraphCollection abstract model, SourceTable equivalent for ArangoDB. 
    """
    graph_dataset = models.ForeignKey(GraphDataset, on_delete=models.CASCADE)
    reference_number = models.IntegerField(null=True)

    class Meta:
        db_table = "app_sourcegraphcollection"
