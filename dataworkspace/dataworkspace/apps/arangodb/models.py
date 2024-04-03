from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from ckeditor.fields import RichTextField
import uuid

from dataworkspace.apps.core.models import (
    DeletableTimestampedUserModel,
)
from dataworkspace.apps.datasets.constants import UserAccessType




class ArangoDataset(DeletableTimestampedUserModel):
    """
    Skeleton Version of ArangoDataset model, Dataset equivalent for ArangoDB. 
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(blank=False, null=False, max_length=128)
    short_description = models.CharField(blank=False, null=False, max_length=256)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)
    description = RichTextField(null=False, blank=False)


    # Permission Management Fields
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
    user_access_type = models.CharField(
        max_length=64,
        choices=UserAccessType.choices,
        default=UserAccessType.REQUIRES_AUTHORIZATION,
    )
    authorized_email_domains = ArrayField(
        models.CharField(max_length=256),
        blank=True,
        default=list,
        help_text="Comma-separated list of domain names without spaces, e.g trade.gov.uk,fco.gov.uk",
    )
    eligibility_criteria = ArrayField(models.CharField(max_length=256), null=True)
    request_approvers = ArrayField(models.CharField(max_length=256), null=True)


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
    collection = models.ForeignKey(ArangoDataset, on_delete=models.CASCADE)

    class Meta:
        db_table = "app_graphdatasetuserpermission"
        unique_together = ("user", "collection")


class SourceGraphCollection(models.Model):
    """
    Skeleton Version of SourceGraphCollection abstract model, SourceTable equivalent for ArangoDB. 
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    graph_dataset = models.ForeignKey(ArangoDataset, on_delete=models.CASCADE)
    name = models.CharField(blank=False, null=False, max_length=128)
    reference_number = models.IntegerField(null=True)

    class Meta:
        db_table = "app_sourcegraphcollection"
