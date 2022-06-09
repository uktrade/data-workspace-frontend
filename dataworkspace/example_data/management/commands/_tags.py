from dataworkspace.apps.datasets.models import Tag
from dataworkspace.apps.datasets.constants import TagType

sources = ["dev", "Superset"]

topics = ["Example Data", "Open Data"]


def get_dev_source_tag():
    tag = Tag.objects.get(name="dev")
    return tag


def get_superset_tag():
    tag = Tag.objects.get(name="Superset")
    return tag


def get_example_topic_tag():
    tag = Tag.objects.get(name="Example Data")
    return tag


def _create_tag(name, type, stdout):
    tag, created = Tag.objects.get_or_create(name=name, type=type)

    stdout.write(
        "%s tag %s was %s"
        % (
            type.name,
            name,
            "created" if created else "updated",
        )
    )

    return tag, created


def create_sample_tags(stdout):

    for source in sources:
        _create_tag(name=source, type=TagType.SOURCE, stdout=stdout)

    for topic in topics:
        _create_tag(topic, TagType.TOPIC, stdout)
