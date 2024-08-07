import uuid
import factory
from dataworkspace.tests.factories import UserFactory
from dataworkspace.apps.core.models import Team, TeamMembership


class TeamFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText(length=20)
    schema_name = factory.fuzzy.FuzzyText(length=20)
    platform = factory.fuzzy.FuzzyChoice(["postgres", "postgres-and-arango"])

    class Meta:
        model = Team


class TeamMembershipFactory(factory.django.DjangoModelFactory):
    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = TeamMembership
