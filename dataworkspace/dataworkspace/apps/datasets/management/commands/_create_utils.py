from django.contrib.auth import get_user_model
from faker import Faker  # noqa


class TestData:
    def __init__(self):
        self.fake = Faker("en-GB")

    def get_dataset_name(self):
        return self.fake.company()

    def get_licence_text(self):
        return "Open Data"

    def get_licence_url(self):
        return self.fake.uri()

    def get_personal_data_text(self):
        return "Does not contain personal data"

    def get_no_restrictions_on_usage_text(self):
        return "No restrictions on usage"

    def get_restrictions_on_usage_text(self):
        return "Entered text must be either OFFICIAL or OFFICIAL-SENSITIVE."

    def get_no_retention_policy_text(self):
        return "No retention policy"

    def get_new_user(self):
        model = get_user_model()

        email = self.fake.ascii_safe_email()
        user = model.objects.create(
            username=email,
            is_staff=False,
            is_superuser=False,
            email=email,
            first_name=self.fake.first_name(),
            last_name=self.fake.last_name(),
        )

        return user

    def get_user(self):
        model = get_user_model()

        user = model.objects.all()

        if user.count():
            return user[0]

        return None
