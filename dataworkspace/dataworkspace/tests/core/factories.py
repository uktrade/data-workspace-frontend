import uuid
import factory
from dataworkspace.apps.core.models import Team


class TeamFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda _: uuid.uuid4())
    name = factory.fuzzy.FuzzyText(length=20)
    schema_name = factory.fuzzy.FuzzyText(length=20)

    class Meta:
        model = Team
