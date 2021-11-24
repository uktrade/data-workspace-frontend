from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


class DatasetsConfig(AppConfig):
    name = "dataworkspace.apps.datasets"

    def ready(self):
        post_migrate.connect(ensure_groups_have_perms, sender=self)


def ensure_groups_have_perms(**_):
    auth_app = apps.get_app_config("auth")
    Group = auth_app.get_model("Group")
    Permission = auth_app.get_model("Permission")
    sme = Group.objects.get_or_create(name="Subject Matter Experts")[0]
    perms = Permission.objects.filter(
        codename__in=[
            "manage_unpublished_master_datasets",
            "manage_unpublished_datacut_datasets",
        ]
    )
    sme.permissions.add(*perms)
    sme.save()
