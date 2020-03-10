import uuid
from datetime import datetime

import factory.fuzzy

from django.contrib.auth import get_user_model
from dataworkspace.apps.datasets.models import DataSet


class UserProfileFactory(factory.django.DjangoModelFactory):
    sso_id = '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2'

    class Meta:
        model = 'accounts.Profile'


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.LazyAttribute(lambda _: f'test.user+{uuid.uuid4()}@example.com')
    password = '12345'

    class Meta:
        model = get_user_model()


class DatabaseFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    memorable_name = 'test_external_db'

    class Meta:
        model = 'core.Database'
        django_get_or_create = ('memorable_name',)


class DataGroupingFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = 'datasets.DataGrouping'


class SourceTagFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()

    class Meta:
        model = 'datasets.SourceTag'


class DataSetFactory(factory.django.DjangoModelFactory):
    grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    deleted = False
    type = DataSet.TYPE_DATA_CUT

    class Meta:
        model = 'datasets.DataSet'


class DataSetUserPermissionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    dataset = factory.SubFactory(DataSetFactory)

    class Meta:
        model = 'datasets.DataSetUserPermission'


class SourceLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    name = factory.fuzzy.FuzzyText()
    format = factory.fuzzy.FuzzyText(length=5)
    frequency = factory.fuzzy.FuzzyText(length=5)
    url = 'http://example.com'

    class Meta:
        model = 'datasets.SourceLink'


class SourceTableFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = 'datasets.SourceTable'


class SourceViewFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = 'datasets.SourceView'


class CustomDatasetQueryFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: n)
    name = factory.fuzzy.FuzzyText()
    dataset = factory.SubFactory(DataSetFactory)
    database = factory.SubFactory(DatabaseFactory)
    reviewed = True
    frequency = 1

    class Meta:
        model = 'datasets.CustomDatasetQuery'


class ReferenceDatasetFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    schema_version = factory.Sequence(lambda n: n)
    table_name = factory.fuzzy.FuzzyText(length=20, prefix='ref_')

    class Meta:
        model = 'datasets.ReferenceDataset'


class ReferenceDatasetFieldFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    name = factory.fuzzy.FuzzyText()
    column_name = factory.fuzzy.FuzzyText(length=65)
    data_type = 1

    class Meta:
        model = 'datasets.ReferenceDatasetField'


class EventLogFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    event_type = 1

    class Meta:
        model = 'eventlog.EventLog'


class ApplicationTemplateFactory(factory.django.DjangoModelFactory):
    name = factory.fuzzy.FuzzyText()
    visible = True
    host_exact = 'testapplication'
    host_pattern = 'testapplication-<user>'
    nice_name = factory.fuzzy.FuzzyText()
    spawner = 'PROCESS'
    spawner_time = int(datetime.timestamp(datetime.now()))
    spawner_options = '{}'
    application_type = 'TOOL'

    class Meta:
        model = 'applications.ApplicationTemplate'
