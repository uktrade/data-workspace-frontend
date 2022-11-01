from django.db import migrations


def map_referencedatasets_to_datasets(apps):
    ReferenceDatasetModel = apps.get_model("datasets", "referencedataset")

    for referencedataset in ReferenceDatasetModel.objects.all():
        referencedataset.save()


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0129_auto_20221031_1449"),
    ]

    operations = [
        migrations.RunPython(map_referencedatasets_to_datasets),
    ]
