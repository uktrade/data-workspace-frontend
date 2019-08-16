import uuid
import factory.fuzzy

from django.contrib.auth import get_user_model


class UserProfileFactory(factory.django.DjangoModelFactory):
    sso_id = '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2'

    class Meta:
        model = 'accounts.Profile'


class UserFactory(factory.django.DjangoModelFactory):
    username = 'test.user@example.com'
    password = '12345'

    class Meta:
        model = get_user_model()


class DatabaseFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    memorable_name = 'test_external_db'

    class Meta:
        model = 'core.Database'


class DataGroupingFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = 'datasets.DataGrouping'


class DataSetFactory(factory.django.DjangoModelFactory):
    volume = 1
    grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True

    class Meta:
        model = 'datasets.DataSet'


class SourceLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    name = factory.fuzzy.FuzzyText()
    format = factory.fuzzy.FuzzyText(length=5)
    frequency = factory.fuzzy.FuzzyText(length=5)
    url = 'http://example.com'

    class Meta:
        model = 'datasets.SourceLink'


class ReferenceDatasetFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True
    schema_version = factory.Sequence(lambda n: n)
    table_name = factory.fuzzy.FuzzyText(length=20)

    class Meta:
        model = 'datasets.ReferenceDataset'


class ReferenceDatasetFieldFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    name = factory.fuzzy.FuzzyText()
    column_name = factory.fuzzy.FuzzyText(length=65)
    data_type = 1

    class Meta:
        model = 'datasets.ReferenceDatasetField'


class ReferenceDatasetExternalDatabaseFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    database = factory.SubFactory(DatabaseFactory)

    class Meta:
        model = 'datasets.ReferenceDatasetExternalDatabase'
