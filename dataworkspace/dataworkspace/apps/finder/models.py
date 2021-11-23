from django.contrib.auth import get_user_model
from django.db import models


class DatasetFinderQueryLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    query = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)
    user = models.ForeignKey(
        get_user_model(), on_delete=models.DO_NOTHING, related_name="finder_searches"
    )

    def __str__(self):
        return "{} – {} – {}".format(
            self.timestamp,
            self.user.get_full_name(),  # pylint: disable=no-member
            self.query,
        )
