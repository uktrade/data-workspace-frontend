# Generated by Django 3.2.5 on 2021-12-15 09:09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("datasets", "0101_auto_20211207_1150"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasetsubscription",
            name="object_id",
            field=models.UUIDField(null=True),
        ),
        migrations.AddField(
            model_name="datasetsubscription",
            name="content_type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="datasetsubscription",
            unique_together={("user", "object_id")},
        ),
        migrations.RemoveField(
            model_name="datasetsubscription",
            name="dataset",
        ),
    ]
