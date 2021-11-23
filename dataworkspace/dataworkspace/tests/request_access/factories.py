import uuid

import factory.fuzzy

from dataworkspace.apps.request_access import models
from dataworkspace.tests.factories import UserFactory


class AccessRequestFactory(factory.django.DjangoModelFactory):
    requester = factory.SubFactory(UserFactory)
    contact_email = factory.LazyAttribute(lambda _: f'test.user+{uuid.uuid4()}@example.com')
    reason_for_access = factory.fuzzy.FuzzyText()

    class Meta:
        model = models.AccessRequest
