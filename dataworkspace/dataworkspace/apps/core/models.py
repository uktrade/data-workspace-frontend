import uuid

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

    def delete(self, **kwargs):
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
