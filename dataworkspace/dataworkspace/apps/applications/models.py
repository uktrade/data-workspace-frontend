import uuid

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

from dataworkspace.apps.core.models import Database, TimeStampedModel


class ApplicationTemplate(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        validators=[RegexValidator(regex=r'^[a-z]+$')],
        max_length=128,
        blank=False,
        help_text='Used in URLs: only lowercase letters allowed',
        unique=True,
    )
    visible = models.BooleanField(default=True, null=False)

    # We expect lots of visualisations with fixed hosts, so we use a undex to ensure
    # that lookups from hostname to application templates are fast...
    host_exact = models.CharField(max_length=128, blank=True, null=False)

    # ... for these, and for tools, we then want to extract information from the hostname,
    # for example the user-id, and use regex to extract this based on the pattern. We
    # could use some of Postgres's regex capability, but suspect it's easier for us to
    # understand and maintain if we just use Python's.
    host_pattern = models.CharField(max_length=128, blank=False)

    nice_name = models.CharField(
        verbose_name='application',
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\- ]+$')],
        max_length=128,
        blank=False,
        unique=True,
    )
    spawner = models.CharField(
        max_length=10,
        choices=(('PROCESS', 'Process'), ('FARGATE', 'Fargate')),
        default='FARGATE',
    )
    spawner_time = models.IntegerField(null=False)
    spawner_options = models.CharField(
        max_length=10240,
        help_text='Options that the spawner understands to start the application',
    )
    application_type = models.CharField(
        max_length=64,
        choices=(
            (
                'VISUALISATION',
                'Visualisation: One instance launched and accessed by all authorized users',
            ),
            ('TOOL', 'Tool: A separate instance launched for each user'),
        ),
        default='TOOL',
    )
    user_access_type = models.CharField(
        max_length=64,
        choices=(
            ('REQUIRES_AUTHENTICATION', 'Requires authentication'),
            ('REQUIRES_AUTHORIZATION', 'Requires authorization'),
        ),
        default='REQUIRES_AUTHENTICATION',
    )

    class Meta:
        db_table = 'app_applicationtemplate'
        indexes = [
            models.Index(fields=['application_type']),
            models.Index(fields=['name']),
            models.Index(fields=['host_exact']),
        ]
        unique_together = ('host_exact', 'host_pattern')

    def __str__(self):
        return self.nice_name


class VisualisationTemplate(ApplicationTemplate):
    class Meta:
        proxy = True
        verbose_name = 'Visualisation'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        self.visible = False
        self.application_type = 'VISUALISATION'

        super(VisualisationTemplate, self).save(
            force_insert, force_update, using, update_fields
        )


class ApplicationInstance(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(get_user_model(), on_delete=models.PROTECT)

    # Stored explicitly to allow matching if URL scheme changed
    public_host = models.CharField(
        max_length=63,
        help_text='The leftmost part of the domain name of this application',
    )

    # Copy of the options to allow for spawners to be changed after (or during) spawning
    application_template = models.ForeignKey(
        ApplicationTemplate, on_delete=models.PROTECT
    )
    spawner = models.CharField(
        max_length=15, help_text='The spawner used to start the application'
    )
    spawner_application_template_options = models.CharField(
        max_length=10240,
        help_text='The spawner options at the time the application instance was spawned',
    )

    spawner_application_instance_id = models.CharField(
        max_length=128,
        help_text='An ID that the spawner understands to control and report on the application',
    )

    # As reported by the spawner
    spawner_created_at = models.DateTimeField(null=True)
    spawner_stopped_at = models.DateTimeField(null=True)
    spawner_cpu = models.CharField(max_length=16, null=True)
    spawner_memory = models.CharField(max_length=16, null=True)

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

    # Fargate expects numerical values for CPU and memory, but boto3 expects
    # them passed as strings. Since these ultimately come as strings from the
    # user, we keep type transformations to a minimum while maintaining
    # flexibility. Fargate will error at runtime if passed something it
    # doesn't understand, so we still get runtime errors even through this is
    # stringly-typed.
    cpu = models.CharField(max_length=16, null=True)  # if not specified by the user
    memory = models.CharField(max_length=16, null=True)  # if not specified by the user

    # The purpose of this field is to raise an IntegrityError if multiple running or spawning
    # instances for the same public host name are created, but to allow multiple stopped or
    # errored
    single_running_or_spawning_integrity = models.CharField(
        max_length=63,
        unique=True,
        help_text='Used internally to avoid duplicate running applications',
    )

    class Meta:
        db_table = 'app_applicationinstance'
        indexes = [
            models.Index(fields=['created_date']),
            models.Index(fields=['owner', 'created_date']),
            models.Index(fields=['public_host', 'state']),
        ]
        permissions = [
            ('start_all_applications', 'Can start all applications'),
            ('access_appstream', 'Can access appstream'),
        ]

    def __str__(self):
        return f'{self.owner} / {self.public_host} / {self.state}'


class ApplicationInstanceDbUsers(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db = models.ForeignKey(Database, on_delete=models.CASCADE)
    db_username = models.CharField(max_length=256)
    application_instance = models.ForeignKey(
        ApplicationInstance, on_delete=models.CASCADE
    )


class ApplicationTemplateUserPermission(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    application_template = models.ForeignKey(
        ApplicationTemplate, on_delete=models.CASCADE
    )

    class Meta:
        db_table = 'app_applicationtemplateuserpermission'
        unique_together = ('user', 'application_template')


class ApplicationInstanceReport(ApplicationInstance):
    class Meta:
        proxy = True
        verbose_name = 'Application report'
        verbose_name_plural = 'Application report'
