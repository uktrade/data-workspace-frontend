import uuid
from django.db import models
from django.core.validators import RegexValidator
from dataworkspace.apps.core.models import TimeStampedModel
from dataworkspace.apps.datasets.models import SourceGraphCollection
from dataworkspace.apps.applications.models import ApplicationInstance


class SourceGraphCollectionFieldDefinition(models.Model):
    """
    Model for defining contents of json fields in collections
    """

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


class ApplicationInstanceArangoUsers(TimeStampedModel):
    """
    Model for tracking temporary user credentials against application instances
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_username = models.CharField(max_length=256)
    application_instance = models.ForeignKey(ApplicationInstance, on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=["db_username"])]
