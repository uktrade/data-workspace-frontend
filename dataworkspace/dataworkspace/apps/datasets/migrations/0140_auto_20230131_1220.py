from django.conf import settings

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("datasets", "0139_add_default_sensitivities"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminVisualisationUserPermission",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "visualisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="datasets.VisualisationCatalogueItem",
                    ),
                ),
            ],
            options={
                "db_table": "app_adminvisualisationuserpermission",
                "unique_together": {("user", "visualisation")},
            },
        ),
    ]
