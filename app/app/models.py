import uuid

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sso_id = models.UUIDField(unique=True, default=uuid.uuid4)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


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
        validators=[RegexValidator(regex=r'[A-Za-z0-9_]')],
        max_length=128,
        blank=False,
        help_text='Must match the set of environment variables starting with DATA_DB__[memorable_name]__',
    )
    is_public = models.BooleanField(
        default=False,
        help_text='If public, the same credentials for the database will be shared with each user. If not public, each user must be explicilty given access, and temporary credentials will be created for each.'
    )

    def __str__(self):
        return f'{self.memorable_name}'


class Privilage(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
        default='public'
    )
    tables = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'(([a-zA-Z][a-zA-Z0-9_\.]*,?)+(?<!,)$)|(^ALL TABLES$)')],
        help_text='Comma-separated list of tables that can be accessed on this schema. "ALL TABLES" (without quotes) to allow access to all tables.',
    )

    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
        unique_together=('user', 'database', 'schema')

    def __str__(self):
        return f'{self.user} / {self.database.memorable_name} / {self.schema} / {self.tables}'
