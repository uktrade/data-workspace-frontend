import sys
from faker import Faker  # noqa
from django.core.management.base import BaseCommand

from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.models import Tag

fake = Faker("en-GB")


class Command(BaseCommand):
    help = "Creates a tag using fake data"

    def add_arguments(self, parser):
        parser.add_argument(
            "type",
            type=str,
            help="Which type of tag to create - [SOURCE, TOPIC]",
        )

        parser.add_argument(
            "count",
            type=int,
            nargs="?",
            default=1,
            help="The number of tags to create (default 1)",
        )

    def handle(self, *args, **options):
        tag_type_text = options["type"].upper()

        if tag_type_text not in TagType.__members__:
            self.stderr.write(self.style.ERROR(f"{options['type']} is not a valid TagType"))
            self.print_help("manage.py", "create_fake_dataset")
            sys.exit(1)

        tag_type = TagType[tag_type_text]
        count = options["count"]

        for x in range(count):
            name = fake.company()

            tag, created = Tag.objects.get_or_create(name=name, type=tag_type)

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{x+1:02}: created new {tag_type.name} tag {name} {tag.id}"
                    )
                )
