# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('explorer', '0002_auto_20150501_1515'),
    ]

    operations = [
        migrations.AddField(
            model_name='query',
            name='snapshot',
            field=models.BooleanField(
                default=False, help_text=b'Include in snapshot task (if enabled)'
            ),
        ),
    ]
