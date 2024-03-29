# Generated by Django 3.0.8 on 2021-01-26 13:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("request_data", "0002_auto_20210125_0925"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datarequest",
            name="requester_role",
            field=models.CharField(
                choices=[
                    ("IAO", "Yes, I am the Information Asset Owner"),
                    ("IAM", "Yes, I am the Information Asset Manager"),
                    ("other", "No, I am someone else"),
                ],
                max_length=256,
            ),
        ),
    ]
