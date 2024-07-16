import pytest

from django.contrib.auth.models import Permission, User
from django.apps import apps
from importlib import import_module
from dataworkspace.tests import factories


@pytest.mark.django_db
class TestDisableToolsMigration:
    def test_user_without_any_tools_permissions_keeps_existing_permissions(self):

        module = import_module("dataworkspace.apps.accounts.migrations.0014_disable_tools")
        user = factories.UserFactory()
        user.user_permissions.set(
            [
                Permission.objects.get(codename="add_masterdataset"),
            ]
        )
        user.save()

        module.remove_tools_access(apps, None)

        loaded_user = User.objects.filter(id=user.id).first()
        assert loaded_user.user_permissions.filter(codename="add_masterdataset").exists()

    @pytest.mark.parametrize(
        "permission_codename",
        (
            ("start_all_applications"),
            ("develop_visualisations"),
            ("access_quicksight"),
            ("access_appstream"),
        ),
    )
    def test_user_with_one_tools_permissions_loses_all_tools_permissions_but_keeps_existing_permissions(
        self, permission_codename
    ):
        tool_permission = Permission.objects.filter(codename=permission_codename).first()

        start_all_applications = Permission.objects.get(codename="start_all_applications")
        develop_visualisations = Permission.objects.get(codename="develop_visualisations")
        access_quicksight = Permission.objects.get(codename="access_quicksight")
        access_appstream = Permission.objects.get(codename="access_appstream")

        module = import_module("dataworkspace.apps.accounts.migrations.0014_disable_tools")
        user_without_tools = factories.UserFactory()

        users_with_tools_ids = []
        for _ in range(0, 5):  # create_batch fails for UserFactory, use a range instead
            user = factories.UserFactory()
            user.user_permissions.set(
                [
                    Permission.objects.get(codename="add_masterdataset"),
                    tool_permission,
                ]
            )
            user.save()
            users_with_tools_ids.append(user.id)

        module.remove_tools_access(apps, None)

        User.objects.filter(id=user_without_tools.id).first()

        loaded_users_with_tools = User.objects.filter(id__in=users_with_tools_ids)
        for loaded_user in loaded_users_with_tools:
            loaded_user = User.objects.filter(id=user.id).first()
            assert loaded_user.user_permissions.filter(codename="add_masterdataset").exists()
            assert not loaded_user.user_permissions.filter(
                codename=start_all_applications.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=develop_visualisations.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=access_quicksight.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=access_appstream.codename
            ).exists()

    def test_user_with_all_tools_permissions_loses_all_tools_permissions_but_keeps_existing_permissions(
        self,
    ):
        start_all_applications = Permission.objects.get(codename="start_all_applications")
        develop_visualisations = Permission.objects.get(codename="develop_visualisations")
        access_quicksight = Permission.objects.get(codename="access_quicksight")
        access_appstream = Permission.objects.get(codename="access_appstream")

        module = import_module("dataworkspace.apps.accounts.migrations.0014_disable_tools")
        user_without_tools = factories.UserFactory()

        users_with_tools_ids = []
        for _ in range(0, 5):  # create_batch fails for UserFactory, use a range instead
            user = factories.UserFactory()
            user.user_permissions.set(
                [
                    Permission.objects.get(codename="add_masterdataset"),
                    start_all_applications,
                    develop_visualisations,
                    access_quicksight,
                    access_appstream,
                ]
            )
            user.save()
            users_with_tools_ids.append(user.id)

        module.remove_tools_access(apps, None)

        User.objects.filter(id=user_without_tools.id).first()

        loaded_users_with_tools = User.objects.filter(id__in=users_with_tools_ids)
        for loaded_user in loaded_users_with_tools:
            loaded_user = User.objects.filter(id=user.id).first()
            assert loaded_user.user_permissions.filter(codename="add_masterdataset").exists()
            assert not loaded_user.user_permissions.filter(
                codename=start_all_applications.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=develop_visualisations.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=access_quicksight.codename
            ).exists()
            assert not loaded_user.user_permissions.filter(
                codename=access_appstream.codename
            ).exists()
