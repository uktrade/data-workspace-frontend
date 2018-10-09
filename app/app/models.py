import uuid

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Database(models.Model):
    # Deliberately no indexes: current plan is only a few public databases.

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    memorable_name = models.CharField(
        max_length=128,
        default='',
    )
    db_name = models.CharField(
        max_length=128,
        blank=False,
    )
    db_host = models.CharField(
        max_length=128,
        blank=False,
    )
    db_port = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(65535)],
        default=5432,
    )
    db_user = models.CharField(
        max_length=128,
        blank=False,
    )

    # These are public datasets: all users will use the same password,
    # they offer only read-only access, and so no need for anything
    # fancier in terms of encryption
    db_password = models.CharField(
        max_length=128,
    )
