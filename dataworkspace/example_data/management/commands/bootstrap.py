from django.core.management.base import BaseCommand
from ._users import create_or_update_admin_user, create_or_update_user
from ._tags import create_sample_tags
from ._datasets import create_example_datasets

ADMIN_EMAIL = "admin.user@example.com"
IAM_EMAIL = "iam.user@example.com"
IAO_EMAIL = "iao.user@example.com"


class Command(BaseCommand):
    help = "Creates or reset a django superuser for admin.user@example.com"

    def write_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def handle(self, *args, **options):
        admin, created = create_or_update_admin_user(
            ADMIN_EMAIL, ADMIN_EMAIL, self.stdout
        )
        self.stdout.write(
            "Admin user: %s was %s"
            % (
                admin,
                "created" if created else "updated",
            )
        )

        iam, created = create_or_update_user(
            IAM_EMAIL, IAM_EMAIL, "Information Asset", "Manager"
        )
        self.stdout.write(
            "IAM: %s was %s"
            % (
                iam,
                "created" if created else "updated",
            )
        )

        iao, created = create_or_update_user(
            IAO_EMAIL, IAO_EMAIL, "Information Asset", "Owner"
        )
        self.stdout.write(
            "IAO: %s was %s"
            % (
                iao,
                "created" if created else "updated",
            )
        )

        self.write_success("Create tags")
        create_sample_tags(self.stdout)

        self.write_success("Create local datasets")
        create_example_datasets(iam, iao, self.stdout)
