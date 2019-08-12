from django.db import migrations, models


def fill_default_to_existing_records(apps, schema_editor):
    SourceLink = apps.get_model('app', 'SourceLink')
    db_alias = schema_editor.connection.alias
    for source_link in SourceLink.objects.using(db_alias).all():
        if not source_link.link_type:
            source_link.link_type = 1  # External
            source_link.save(update_fields=['link_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0037_merge_20190807_1109'),
    ]

    operations = [
        migrations.RunPython(fill_default_to_existing_records, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sourcelink',
            name='link_type',
            field=models.IntegerField(choices=[(1, 'External Link'), (2, 'Local Link')], default=1),
        ),
    ]
