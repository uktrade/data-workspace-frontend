# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("explorer", "0005_auto_20160105_2052"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="connection",
            field=models.CharField(
                help_text=b"Name of DB connection (as specified in settings) to use for this query."
                b" Will use EXPLORER_DEFAULT_CONNECTION if left blank",
                max_length=128,
                null=True,
                blank=True,
            ),
        ),
    ]
