import uuid

from django.db import models


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
        ResponsiblePerson, on_delete=models.PROTECT, related_name='asset_owner', null=True, blank=True)
    information_asset_manager = models.ForeignKey(
        ResponsiblePerson, on_delete=models.PROTECT, related_name='asset_manager', null=True, blank=True)

    slug = models.SlugField(max_length=50, db_index=True, unique=True, null=False, blank=False)

    audience = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.name}'


class DataSet(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(blank=False, null=False, max_length=128)
    slug = models.SlugField(max_length=50, db_index=True, null=False, blank=False)

    short_description = models.CharField(
        blank=False, null=False, max_length=256)

    grouping = models.ForeignKey(DataGrouping, on_delete=models.CASCADE)

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    description = models.TextField(null=False, blank=False)

    enquiries_contact = models.ForeignKey(
        ResponsiblePerson, on_delete=models.PROTECT)

    reference = models.CharField(null=False, blank=False, max_length=128)
    redactions = models.TextField(null=True, blank=True)
    licence = models.CharField(null=True, blank=True, max_length=256)

    volume = models.IntegerField(null=False, blank=False)

    retention_policy = models.TextField(null=True, blank=True)
    personal_data = models.CharField(null=True, blank=True, max_length=128)

    def __str__(self):
        return f'{self.name}'


class DataLink(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    dataset = models.ForeignKey(DataSet, on_delete=models.PROTECT)

    name = models.CharField(blank=False, null=False, max_length=256)
    format = models.CharField(blank=False, null=False, max_length=10)
    url = models.CharField(blank=True, null=True, max_length=1024)

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    frequency = models.CharField(blank=False, null=False, max_length=50)

