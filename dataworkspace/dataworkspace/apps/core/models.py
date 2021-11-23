import re
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import pre_delete, post_delete
from django.core.validators import RegexValidator
from django.conf import settings


class TimeStampedModel(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DeletableQuerySet(models.Manager):
    def live(self):
        """
        Returns objects that have not been deleted
        :return:
        """
        return self.get_queryset().filter(deleted=False)


class DeletableModel(models.Model):
    deleted = models.BooleanField(default=False)
    objects = DeletableQuerySet()

    class Meta:
        abstract = True

    def delete(self, **kwargs):  # pylint: disable=arguments-differ
        """
        Override delete method to allow for "soft" deleting.
        If `force` is True delete from the database, otherwise set model.deleted = True
        :param kwargs: dict - add force=True to delete from the database
        :return:
        """
        force = kwargs.pop('force', False)
        if force:
            super().delete(**kwargs)
        else:
            pre_delete.send(self.__class__, instance=self)
            self.deleted = True
            self.save()
            post_delete.send(self.__class__, instance=self)


class UserLogModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created+',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated+',
    )

    class Meta:
        abstract = True


class TimeStampedUserModel(TimeStampedModel, UserLogModel):
    class Meta:
        abstract = True


class DeletableTimestampedUserModel(DeletableModel, TimeStampedUserModel):
    class Meta:
        abstract = True


class Database(TimeStampedModel):
    # Deliberately no indexes: current plan is only a few public databases.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    memorable_name = models.CharField(
        validators=[RegexValidator(regex=r'[A-Za-z0-9_]')],
        max_length=128,
        blank=False,
        unique=True,
        help_text='Must match the set of environment variables starting with DATA_DB__[memorable_name]__',
    )
    is_public = models.BooleanField(
        default=False,
        help_text=(
            'If public, the same credentials for the database will be shared with each user. '
            'If not public, each user must be explicilty given access, '
            'and temporary credentials will be created for each.'
        ),
    )

    class Meta:
        db_table = 'app_database'

    def __str__(self):
        return f'{self.memorable_name}'


class DatabaseUser(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='db_user'
    )
    username = models.CharField(max_length=256)
    deleted_date = models.DateTimeField(null=True, blank=True)


class HowSatisfiedType(models.TextChoices):
    very_satified = 'very-satified', 'Very satisfied'
    satified = 'satified', 'Satisfied'
    neither = 'neither', 'Neither satisfied nor dissatisfied'
    dissatisfied = 'dissatisfied', 'Dissatisfied'
    very_dissatisfied = 'very-dissatisfied', 'Very dissatisfied'


class TryingToDoType(models.TextChoices):
    looking = 'looking', 'Looking for data'
    access_data = 'access-data', 'Trying to access data'
    analyse_data = 'analyse-data', 'Analyse data'
    use_tool = 'use-tool', 'Use a tool'
    create_visualisation = 'create-visualisation', 'Create a data visualisation'
    share_date = 'share-date', 'Share data'
    share_visualisation = 'share-visualisation', 'Share a data visualisation'
    view_visualisation = 'view-visualisation', 'View a data visualisation'
    other = 'other', 'Other'
    dont_know = 'dont-know', 'Don’t know'


class UserSatisfactionSurvey(TimeStampedModel):
    how_satisfied = models.CharField(max_length=32, choices=HowSatisfiedType.choices)
    trying_to_do = models.TextField(null=True, blank=True, choices=TryingToDoType.choices)
    improve_service = models.TextField(null=True, blank=True)


class Team(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256, unique=True)
    schema_name = models.CharField(max_length=63, unique=True)

    member = models.ManyToManyField(get_user_model(), through="TeamMembership")

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.schema_name:
            self.schema_name = '_team_' + re.sub('[^a-z0-9]', '_', self.name.lower())[:63]
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class TeamMembership(TimeStampedModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name='team_memberships'
    )

    class Meta:
        unique_together = ("team_id", "user_id")
