import uuid

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse

from dataworkspace.apps.core.models import DeletableTimestampedUserModel, RichTextField
from dataworkspace.apps.core.models import get_user_model
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

    def get_absolute_url(self):
        return reverse("data_collections:collections_view", args=(self.id,))

    def datasets_count(self, obj):
        return obj.datasets_count

    def dashboards_count(self, obj):
        return obj.dashboards_count

    def users_count(self, obj):
        return obj.users_count

    def notes_added(self):
        return bool(self.notes)

    notes_added.boolean = True

    datasets_count.admin_order_field = "datasets_count"
    datasets_count.description = "Datasets count"

    dashboards_count.admin_order_field = "dashboards_count"
    dashboards_count.description = "Dashboards count"

    users_count.admin_order_field = "users_count"
    users_count.description = "Users count"

    notes_added.order_field = "notes"
    notes_added.description = "Notes truncated"


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
                deleted_by,
                EventLog.TYPE_REMOVE_DATASET_FROM_COLLECTION,
                related_object=self.collection,
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
                deleted_by,
                EventLog.TYPE_REMOVE_VISUALISATION_FROM_COLLECTION,
                related_object=self.collection,
            )


class CollectionUserMembership(DeletableTimestampedUserModel):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="collection_memberships"
    )
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
            log_event(
                deleted_by,
                EventLog.TYPE_REMOVE_USER_FROM_COLLECTION,
                related_object=self.collection,
                extra={
                    "removed_user": {
                        "id": self.user.id,  # pylint: disable=no-member
                        "email": self.user.email,  # pylint: disable=no-member
                        "name": self.user.get_full_name(),  # pylint: disable=no-member
                    }
                },
            )
