from django.db import models

from dataworkspace.apps.core.models import (
    TimeStampedUserModel,
)


class UploadedTable(TimeStampedUserModel):
    schema = models.TextField()
    table_name = models.TextField()
    data_flow_execution_date = models.DateTimeField()

    def display_name(self):
        return f"{self.schema}.{self.table_name}"
