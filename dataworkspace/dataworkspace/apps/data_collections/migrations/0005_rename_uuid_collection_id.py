# Generated by Django 3.2.15 on 2022-10-27 12:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("data_collections", "0004_auto_20221027_1239"),
    ]

    operations = [
        migrations.RenameField(
            model_name="collection",
            old_name="uuid",
            new_name="id",
        ),
    ]
