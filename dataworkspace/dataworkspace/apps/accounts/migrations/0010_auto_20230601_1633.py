# Generated by Django 3.2.19 on 2023-06-01 16:33

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_alter_userdatatableview_user"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userdatatableview",
            name="sort_column",
        ),
        migrations.RemoveField(
            model_name="userdatatableview",
            name="sort_direction",
        ),
        migrations.RemoveField(
            model_name="userdatatableview",
            name="visible_columns",
        ),
        migrations.AddField(
            model_name="userdatatableview",
            name="column_defs",
            field=models.JSONField(default={}),
        ),
    ]
