from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.utils import find_dataset


class Command(BaseCommand):
    help = "Map security classification to dataset"

    def add_arguments(self, parser):
        parser.add_argument("--email",
                            dest="email")
        parser.add_argument("--dataset_uuid",
                            help="DataSet UUID",
                            dest="dataset_uuid",
                            )
        parser.add_argument(
            "--government_security_classification",
            help="Security classification - 1: Official . 2: Official-sensitive",
            dest="government_security_classification",
            type=int,
        )
        parser.add_argument(
            "--sensitivity",
            help="Sensitivity (array)",
            nargs="*",
            dest="sensitivity",
        )

    def handle(self, *args, **options):
        _User = get_user_model()
        user = _User.objects.filter(email=options["email"]).first()

        if user is None:
            self.stdout.write(
                self.style.ERROR(
                    "Cannot find user with email address {}".format(options["email"])
                )
            )
            return

        dataset = find_dataset(options["dataset_uuid"], user)

        dataset.government_security_classification = options["government_security_classification"]
        dataset.sensitivity.clear()

        for sensitivity_type in list(options["sensitivity"]):
            dataset.sensitivity.add(sensitivity_type)

        dataset.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Dataset {} had the correct security classification added".format(
                    dataset
                )
            )
        )
