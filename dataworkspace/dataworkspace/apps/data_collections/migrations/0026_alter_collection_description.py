# Generated by Django 4.2.15 on 2024-08-16 15:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_collections", "0025_alter_collection_description"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collection",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
    ]
