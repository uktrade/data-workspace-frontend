# Generated by Django 3.2.16 on 2022-11-15 11:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0132_alter_dataset_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataset",
            name="type",
            field=models.IntegerField(
                choices=[(1, "Source dataset"), (2, "Data cut"), (0, "Reference dataset")],
                default=2,
            ),
        ),
    ]