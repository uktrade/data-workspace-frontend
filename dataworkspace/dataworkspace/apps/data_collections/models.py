import uuid

from ckeditor.fields import RichTextField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Q

from dataworkspace.apps.core.models import DeletableTimestampedUserModel
from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event


class Collection(DeletableTimestampedUserModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(blank=False, null=False, max_length=128)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    datasets = models.ManyToManyField(DataSet, through="CollectionDatasetMembership")
    visualisation_catalogue_items = models.ManyToManyField(
        VisualisationCatalogueItem,
        through="CollectionVisualisationCatalogueItemMembership",
    )
    notes = RichTextField(null=True, blank=True)

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"

    def __str__(self):
        return self.name


class CollectionDatasetMembership(DeletableTimestampedUserModel):
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name="datasets")
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="dataset_collections"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset_id", "collection_id"],
                condition=Q(deleted=False),
                name="unique_dataset_if_not_deleted",
            )
        ]
        ordering = ("id",)

    def delete(self, deleted_by, **kwargs):  # pylint: disable=arguments-differ
        with transaction.atomic():
            super().delete(**kwargs)
            log_event(
                deleted_by, EventLog.TYPE_REMOVE_DATASET_FROM_COLLECTION, related_object=self
            )


class CollectionVisualisationCatalogueItemMembership(DeletableTimestampedUserModel):
    visualisation = models.ForeignKey(
        VisualisationCatalogueItem, on_delete=models.CASCADE, related_name="visualisation"
    )
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="visualisation_collections"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["visualisation", "collection_id"],
                condition=Q(deleted=False),
                name="unique_visualisation_if_not_deleted",
            )
        ]
        ordering = ("id",)

    def delete(self, deleted_by, **kwargs):  # pylint: disable=arguments-differ
        with transaction.atomic():
            super().delete(**kwargs)
            log_event(
                deleted_by, EventLog.TYPE_REMOVE_VISUALISATION_FROM_COLLECTION, related_object=self
            )


class CollectionUserMembership(DeletableTimestampedUserModel):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="users")
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="user_memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "collection_id"],
                condition=Q(deleted=False),
                name="unique_user_if_not_deleted",
            )
        ]
        ordering = ("id",)

    def delete(self, deleted_by, **kwargs):  # pylint: disable=arguments-differ
        with transaction.atomic():
            super().delete(**kwargs)
            log_event(deleted_by, EventLog.TYPE_REMOVE_USER_FROM_COLLECTION, related_object=self)
