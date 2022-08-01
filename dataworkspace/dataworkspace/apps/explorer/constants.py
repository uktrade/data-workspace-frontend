from django.db import models


class QueryLogState(models.IntegerChoices):
    RUNNING = 0, "Running"
    FAILED = 1, "Failed"
    COMPLETE = 2, "Complete"
    CANCELLED = 3, "Cancelled"
