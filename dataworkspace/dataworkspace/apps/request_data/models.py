from django.conf import settings
from django.db import models

from dataworkspace.apps.core.models import (  # pylint: disable=import-error
    TimeStampedModel,
)


class RoleType(models.TextChoices):
    IAO = "IAO", "Yes, I am the Information Asset Owner"
    IAM = "IAM", "Yes, I am the Information Asset Manager"
    other = "other", "No, I am someone else"


class SecurityClassificationType(models.TextChoices):
    official = "official", "Official (includes public data)"
    commercial = "commercially-sensitive", "Official-Sensitive Commercial"
    personal = "personal", "Official-Sensitive Personal"
    locsen = "locsen", "Official-Sensitive LocSen (location sensitive)"
    secret = "secret", "Secret"
    top_secret = "top-secret", "Top secret"
    unknown = "unknown", "I don’t know"


class DataRequestStatus(models.TextChoices):
    draft = "draft"
    submitted = "submitted"


class DataRequest(TimeStampedModel):
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="data_requests",
    )
    requester_role = models.CharField(max_length=256, choices=RoleType.choices)
    name_of_owner_or_manager = models.CharField(max_length=256, blank=True)
    data_description = models.TextField()
    data_purpose = models.TextField()
    data_location = models.TextField(blank=True)
    data_licence = models.TextField(blank=True)
    security_classification = models.CharField(
        max_length=256, choices=SecurityClassificationType.choices
    )
    status = models.CharField(
        max_length=256,
        choices=DataRequestStatus.choices,
        default=DataRequestStatus.draft,
    )
    help_desk_ticket_id = models.CharField(max_length=256)
