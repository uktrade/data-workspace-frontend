# Generated by Django 3.2.19 on 2023-05-31 15:49

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("request_access", "0005_migrate_auth_user_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accessrequest",
            name="requester",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
