# Generated by Django 4.2.15 on 2025-01-23 09:50
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notification_banner", "0005_alter_notificationbanner_end_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationbanner",
            name="end_date",
            field=models.DateField(),
        ),
    ]
