import datetime
from uuid import uuid4

import pytest
from faker import Faker


@pytest.fixture
def sso_user_factory():

    faker = Faker()

    def _factory(published_date=None):
        published_date = datetime.datetime.today() if published_date is None else published_date
        return {
            "published": published_date.strftime("%Y%m%dT%H%M%S.%dZ"),
            "object": {
                "dit:StaffSSO:User:userId": str(uuid4()),
                "dit:emailAddress": [faker.email()],
                "dit:firstName": faker.first_name(),
                "dit:lastName": faker.last_name(),
                "dit:StaffSSO:User:status": "active",
            },
        }

    return _factory
