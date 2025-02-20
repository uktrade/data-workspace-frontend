# Generated by Django 4.2.16 on 2024-10-24 08:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0025_applicationtemplate_include_in_dw_stats"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usertoolconfiguration",
            name="size",
            field=models.IntegerField(
                choices=[
                    (1, "Small"),
                    (2, "Medium"),
                    (3, "Large"),
                    (4, "Extra Large"),
                    (5, "2x Extra Large"),
                ],
                default=2,
            ),
        ),
    ]
