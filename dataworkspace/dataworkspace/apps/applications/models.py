import uuid

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

from dataworkspace.apps.core.models import TimeStampedModel


class ApplicationTemplate(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        validators=[RegexValidator(regex=r'^[a-z]+$')],
        max_length=128,
        blank=False,
        help_text='Used in URLs: only lowercase letters allowed',
        unique=True,
    )
    nice_name = models.CharField(
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\- ]+$')],
        max_length=128,
        blank=False,
        unique=True,
    )
    spawner = models.CharField(
        max_length=10,
        choices=(
            ('PROCESS', 'Process'),
        ),
        default='PROCESS',
    )
    spawner_options = models.CharField(
        max_length=10240,
        help_text='Options that the spawner understands to start the application',
    )

    class Meta:
        db_table = "app_applicationtemplate"
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f'{self.name}'


class ApplicationInstance(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(get_user_model(), on_delete=models.PROTECT)

    # Stored explicitly to allow matching if URL scheme changed
    public_host = models.CharField(
        max_length=63,
        help_text='The leftmost part of the domain name of this application',
    )

    # Copy of the options to allow for spawners to be changed after (or during) spawning
    application_template = models.ForeignKey(ApplicationTemplate, on_delete=models.PROTECT)
    spawner = models.CharField(
        max_length=15,
        help_text='The spawner used to start the application',
    )
    spawner_application_template_options = models.CharField(
        max_length=10240,
        help_text='The spawner options at the time the application instance was spawned',
    )

    spawner_application_instance_id = models.CharField(
        max_length=128,
        help_text='An ID that the spawner understands to control and report on the application',
    )

    state = models.CharField(
        max_length=16,
        choices=(
            ('SPAWNING', 'Spawning'),
            ('RUNNING', 'Running'),
            ('STOPPED', 'Stopped'),
        ),
        default='SPAWNING',
    )
    proxy_url = models.CharField(
        max_length=256,
        help_text='The URL that the proxy can proxy HTTP and WebSockets requests to',
    )

    # The purpose of this field is to raise an IntegrityError if multiple running or spawning
    # instances for the same public host name are created, but to allow multiple stopped or
    # errored
    single_running_or_spawning_integrity = models.CharField(
        max_length=63,
        unique=True,
        help_text='Used internally to avoid duplicate running applications'
    )

    class Meta:
        db_table = "app_applicationinstance"
        indexes = [
            models.Index(fields=['owner', 'created_date']),
            models.Index(fields=['public_host', 'state']),
        ]
        permissions = [
            ('start_all_applications', 'Can start all applications'),
            ('access_appstream', 'Can access appstream'),
        ]

    def __str__(self):
        return f'{self.owner} / {self.public_host} / {self.state}'
