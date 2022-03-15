import factory

from dataworkspace.apps.explorer import models
from dataworkspace.tests.factories import UserFactory


class SimpleQueryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Query

    title = factory.Sequence(lambda n: "My simple query %s" % n)
    sql = "SELECT 1+1 AS TWO"  # same result in postgres and sqlite
    description = "Doin' math"
    connection = "my_database"
    created_by_user = factory.SubFactory(UserFactory)


class QueryLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.QueryLog

    sql = "SELECT 2+2 AS FOUR"
    page = 1
    duration = 1000
    connection = "my_database"


class PlaygroundSQLFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.PlaygroundSQL

    sql = "SELECT 1+2 AS THREE"
    created_by_user = factory.SubFactory(UserFactory)


class ChartBuilderChartFactory(factory.django.DjangoModelFactory):
    query_log = factory.SubFactory(QueryLogFactory)
    created_by = factory.SubFactory(UserFactory)
    updated_by = factory.SubFactory(UserFactory)
    title = factory.fuzzy.FuzzyText(length=20)
    description = factory.fuzzy.FuzzyText(length=50)

    class Meta:
        model = models.ChartBuilderChart
