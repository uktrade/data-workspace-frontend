import uuid
import factory
import factory.fuzzy
from django.contrib.auth.models import User


class UserProfileFactory(factory.django.DjangoModelFactory):
    sso_id = '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2'

    class Meta:
        model = 'app.Profile'


class UserFactory(factory.django.DjangoModelFactory):
    username = 'test.user@example.com'
    password = '12345'

    class Meta:
        model = User


class DataGroupingFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)

    class Meta:
        model = 'app.DataGrouping'


class DataSetFactory(factory.django.DjangoModelFactory):
    volume = 1
    grouping = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True

    class Meta:
        model = 'app.DataSet'


class SourceLinkFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    dataset = factory.SubFactory(DataSetFactory)
    name = factory.fuzzy.FuzzyText()
    format = factory.fuzzy.FuzzyText(length=5)
    frequency = factory.fuzzy.FuzzyText(length=5)
    url = 'http://example.com'

    class Meta:
        model = 'app.SourceLink'


class ReferenceDatasetFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(DataGroupingFactory)
    name = factory.fuzzy.FuzzyText()
    slug = factory.fuzzy.FuzzyText(length=10)
    published = True

    class Meta:
        model = 'app.ReferenceDataset'


class ReferenceDatasetFieldFactory(factory.django.DjangoModelFactory):
    reference_dataset = factory.SubFactory(ReferenceDatasetFactory)
    name = factory.fuzzy.FuzzyText()
    data_type = 1

    class Meta:
        model = 'app.ReferenceDatasetField'
