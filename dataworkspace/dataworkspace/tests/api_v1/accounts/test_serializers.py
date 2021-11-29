import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.serializers import Serializer

from dataworkspace.tests import factories
from dataworkspace.apps.api_v1.accounts.serializers import UserSerializer


@pytest.mark.django_db
class TestUserSerializer:
    factory = factories.UserFactory

    def test_permissions_subset_is_all_false(self):
        user = self.factory()
        serializer = UserSerializer(user)
        serialized_data = serializer.data
        user_permissions_subset = serialized_data["user_permissions_subset"]
        assert user_permissions_subset == {
            "develop_visualisations": False,
            "access_quicksight": False,
            "start_all_applications": False,
            "access_appstream": False,
        }

    def test_permissions_subset_can_access_appstream(self):
        user = self.factory()
        permission = Permission.objects.create(
            codename="access_appstream",
            content_type=ContentType.objects.get_for_model(user),
        )
        user.user_permissions.add(permission)
        serializer = UserSerializer(user)
        serialized_data = serializer.data
        user_permissions_subset = serialized_data["user_permissions_subset"]
        assert user_permissions_subset == {
            "develop_visualisations": False,
            "access_quicksight": False,
            "start_all_applications": False,
            "access_appstream": True,
        }

