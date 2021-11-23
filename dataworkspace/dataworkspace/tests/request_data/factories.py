import random

import factory

from dataworkspace.apps.request_data import models
from dataworkspace.tests.factories import UserFactory


class DataRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.DataRequest

    requester = factory.SubFactory(UserFactory)
    requester_role = factory.LazyFunction(lambda: random.choice(models.RoleType.choices)[0])
    data_description = factory.Faker("paragraph")
    data_purpose = factory.Faker("paragraph")
    data_location = factory.Faker("paragraph")
    security_classification = factory.LazyFunction(
        lambda: random.choice(models.SecurityClassificationType.choices)[0]
    )
    name_of_owner_or_manager = factory.Faker("name")
    status = factory.LazyFunction(lambda: random.choice(models.DataRequestStatus.choices)[0])
