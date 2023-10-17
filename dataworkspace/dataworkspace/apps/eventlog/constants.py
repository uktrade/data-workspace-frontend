from django.db import models


class SystemStatLogEventType(models.IntegerChoices):
    PERMISSIONS_QUERY_RUNTIME = 1, "Runtime to generate tool table permissions for a user"
