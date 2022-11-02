import uuid

from django.conf import settings
from django.db import models, transaction

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
    published = models.BooleanField(default=False)
    datasets = models.ManyToManyField(DataSet, through="CollectionDatasetMembership")
    visualisation_catalogue_items = models.ManyToManyField(
        VisualisationCatalogueItem,
        through="CollectionVisualisationCatalogueItemMembership",
    )

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
        unique_together = ("dataset_id", "collection_id")
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
        unique_together = ("visualisation", "collection_id")
        ordering = ("id",)

    def delete(self, deleted_by, **kwargs):  # pylint: disable=arguments-differ
        with transaction.atomic():
            super().delete(**kwargs)
            log_event(
                deleted_by, EventLog.TYPE_REMOVE_VISUALISATION_FROM_COLLECTION, related_object=self
            )
