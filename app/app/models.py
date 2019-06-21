import uuid

from django.conf import settings
from django.contrib.auth.models import (
    User,
    Permission,
)
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sso_id = models.UUIDField(unique=True, default=uuid.uuid4)


@receiver(post_save, sender=User)
def save_user_profile(instance, **_):
    try:
        profile = instance.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=instance)
    profile.save()


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
        unique=True,
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
        unique_together = ('user', 'database', 'schema')

    def __str__(self):
        return f'{self.user} / {self.database} / {self.schema} / {self.tables}'


class ApplicationTemplate(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

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
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f'{self.name}'


class ApplicationInstance(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey(User, on_delete=models.PROTECT)

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
        indexes = [
            models.Index(fields=['owner', 'created_date']),
            models.Index(fields=['public_host', 'state']),
        ]
        permissions = [
            ('start_all_applications', 'Can start all applications'),
        ]

    def __str__(self):
        return f'{self.owner} / {self.public_host} / {self.state}'


class ResponsiblePerson(models.Model):
    email = models.EmailField(primary_key=True)
    name = models.CharField(null=False, blank=False, max_length=128)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} <{self.email}>'


class DataGrouping(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    # 128 - small tweet in length
    name = models.CharField(unique=True, blank=False,
                            null=False, max_length=128)
    # 256 i.e. a long tweet length
    short_description = models.CharField(
        blank=False, null=False, max_length=256)
    description = models.TextField(blank=True, null=True)

    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_owner',
        null=True,
        blank=True
    )

    information_asset_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_manager',
        null=True,
        blank=True
    )

    slug = models.SlugField(max_length=50, db_index=True, unique=True, null=False, blank=False)

    audience = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class DataSet(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
    )
    required_permissions = models.ManyToManyField(Permission)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)

    short_description = models.CharField(
        blank=False, null=False, max_length=256)

    grouping = models.ForeignKey(DataGrouping, on_delete=models.CASCADE)

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    description = models.TextField(null=False, blank=False)

    enquiries_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    redactions = models.TextField(null=True, blank=True)
    licence = models.CharField(null=True, blank=True, max_length=256)

    volume = models.IntegerField(null=False, blank=False)

    retention_policy = models.TextField(null=True, blank=True)
    personal_data = models.CharField(null=True, blank=True, max_length=128)

    restrictions_on_usage = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        permissions = [
            ('security_clearance', 'Security clearance'),
        ]


class SourceSchema(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    dataset = models.ForeignKey(
        DataSet,
        # We expect a single schema per DataSet, but do not use OneToOneField
        # for explicit compatibility with other Source types
        unique=True,
        on_delete=models.CASCADE,
    )
    database = models.ForeignKey(
        Database,
        default=None,
        on_delete=models.CASCADE,
    )
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
        default='public'
    )


class SourceTables(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )
    database = models.ForeignKey(
        Database,
        default=None,
        on_delete=models.CASCADE,
    )
    schema = models.CharField(
        max_length=1024,
        blank=False,
        validators=[RegexValidator(regex=r'^[a-zA-Z][a-zA-Z0-9_\.]*$')],
        default='public'
    )
    tables = models.CharField(
        max_length=1024,
        blank=False,
        # ALL TABLES is for backwards compatibility
        validators=[RegexValidator(regex=r'(([a-zA-Z][a-zA-Z0-9_\.]*,?)+(?<!,)$)|(^ALL TABLES$)')],
        help_text='Comma-separated list of tables that can be accessed on this schema. "ALL TABLES" (without quotes) to allow access to all tables.',
    )


class SourceLink(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        blank=False,
        null=False,
        max_length=128,
    )
    url = models.CharField(
        max_length=256,
    )

    format = models.CharField(blank=False, null=False, max_length=10)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    frequency = models.CharField(blank=False, null=False, max_length=50)
