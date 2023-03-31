import factory

from dataworkspace.apps.core.charts.models import ChartBuilderChart
from dataworkspace.tests.explorer.factories import QueryLogFactory
from dataworkspace.tests.factories import UserFactory


class ChartBuilderChartFactory(factory.django.DjangoModelFactory):
    query_log = factory.SubFactory(QueryLogFactory)
    created_by = factory.SubFactory(UserFactory)
    updated_by = factory.SubFactory(UserFactory)
    title = factory.fuzzy.FuzzyText(length=20)
    description = factory.fuzzy.FuzzyText(length=50)

    class Meta:
        model = ChartBuilderChart


class TeamFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText(length=20)
    schema_name = factory.fuzzy.FuzzyText(length=20)

    class Meta:
        model = Team
