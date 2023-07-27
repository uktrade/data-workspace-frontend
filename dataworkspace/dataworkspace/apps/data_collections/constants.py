from django.db import models


class CollectionUserAccessType(models.TextChoices):
    REQUIRES_AUTHENTICATION = "REQUIRES_AUTHENTICATION", "All logged in users"
    REQUIRES_AUTHORIZATION = (
        "REQUIRES_AUTHORIZATION",
        "Only specific authorized users or email domains",
    )
