from django.contrib.auth import get_user_model
from django.db import models

from dataworkspace.apps.core.models import TimeStampedUserModel


class UploadedTable(TimeStampedUserModel):
    schema = models.TextField()
    table_name = models.TextField()
    data_flow_execution_date = models.DateTimeField()

    def display_name(self):
        return f"{self.schema}.{self.table_name}"


class YourFilesUserPrefixStats(models.Model):
    user = models.ForeignKey(
        get_user_model(), related_name="your_files_stats", on_delete=models.CASCADE
    )
    prefix = models.CharField(max_length=255, db_index=True)
    total_size_bytes = models.BigIntegerField()
    num_files = models.IntegerField()
    num_large_files = models.IntegerField()
    created_date = models.DateTimeField(auto_now_add=True)
    last_checked_date = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "created_date"
        ordering = ("-created_date",)
