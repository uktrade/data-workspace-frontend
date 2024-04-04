from django.db import models
from django.core.validators import RegexValidator
import uuid
from dataworkspace.apps.datasets.models import ReferenceNumberedDatasetSource


class SourceGraphCollection(ReferenceNumberedDatasetSource):
    """
    Model for collections stored in the Arango Database
    """

    # From Bypassing BaseSource
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=1024,
        blank=False,
        help_text="Used as the displayed text in the download link",
    )
    collection = models.CharField(
        max_length=1024,
        blank=False,
        default="Empty",
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
        db_index=True,
    )
    dataset_finder_opted_in = models.BooleanField(
        default=False,
        null=False,
        verbose_name="IAM/IAO opt-in for Dataset Finder",
        help_text=(
            "Should this dataset be discoverable through Dataset Finder for all users, "
            "even if they haven’t been explicitly granted access?"
        ),
    )
    data_grid_enabled = models.BooleanField(
        default=True,
        help_text="Allow users to filter, sort and export data from within the browser",
    )
    published = models.BooleanField(
        default=True,
        help_text=("When false hides source table from catalogue page"),
    )

    class Meta:
        db_table = "app_sourcegraphcollection"

    def __str__(self):
        return f"{self.name} ({self.id})"
    

class SourceGraphCollectionFieldDefinition(models.Model):
    field = models.CharField(
        max_length=63,
        blank=False,
        validators=[RegexValidator(regex=r"^[a-zA-Z][a-zA-Z0-9_\.]*$")],
    )
    description = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
    )
    source_collection = models.ForeignKey(
        SourceGraphCollection,
        on_delete=models.CASCADE,
        related_name="field_definitions",
    )

    class Meta:
        unique_together = (
            "field",
            "source_collection",
        )
 