from django.conf import settings
from django.db import models
from django.db.models.signals import pre_delete, post_delete


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
        related_name='created+'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated+'
    )

    class Meta:
        abstract = True


class TimeStampedUserModel(TimeStampedModel, UserLogModel):
    class Meta:
        abstract = True


class DeletableTimestampedUserModel(DeletableModel, TimeStampedUserModel):
    class Meta:
        abstract = True
