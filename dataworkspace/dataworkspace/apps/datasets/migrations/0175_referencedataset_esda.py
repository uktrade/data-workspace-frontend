# Generated by Django 4.2.15 on 2024-09-16 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0174_dataset_esda"),
    ]

    operations = [
        migrations.AddField(
            model_name="referencedataset",
            name="esda",
            field=models.BooleanField(default=True),
        ),
    ]