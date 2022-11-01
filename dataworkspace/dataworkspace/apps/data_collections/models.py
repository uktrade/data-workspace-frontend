import uuid

from django.conf import settings
from django.db import models

from dataworkspace.apps.core.models import DeletableTimestampedUserModel, TimeStampedModel
from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem


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


class CollectionDatasetMembership(TimeStampedModel):
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name="datasets")
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="dataset_collections"
    )

    class Meta:
        unique_together = ("dataset_id", "collection_id")
        ordering = ("id",)


class CollectionVisualisationCatalogueItemMembership(TimeStampedModel):
    visualisation = models.ForeignKey(
        VisualisationCatalogueItem, on_delete=models.CASCADE, related_name="visualisation"
    )
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="visualisation_collections"
    )

    class Meta:
        unique_together = ("visualisation", "collection_id")
        ordering = ("id",)
