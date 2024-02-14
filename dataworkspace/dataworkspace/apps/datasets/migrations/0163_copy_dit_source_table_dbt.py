from django.db import migrations


def copy_schema_dit_dbt(apps, _):
    source_table_model = apps.get_model("datasets", "SourceTable")
    for source_table in source_table_model.objects.filter(schema="dit").all():
        source_table.id = None
        source_table.schema = "dbt"
        source_table.save()


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0162_merge_20231227_1128"),
    ]

    operations = [
        migrations.RunPython(copy_schema_dit_dbt, reverse_code=migrations.RunPython.noop),
    ]