from django.db import migrations
from django.db.models import F, Func, Value


def replace_func(field_name, find_str, replace_str):
    return Func(F(field_name), Value(find_str), Value(replace_str), function="replace")


def migrate_schema_dit_dbt(apps, _):
    datacut_model = apps.get_model("datasets", "CustomDatasetQuery")
    datacut_model.objects.update(name=replace_func("query", "dit.", "dbt."))

    datacut_query_table_model = apps.get_model("datasets", "CustomDatasetQueryTable")
    for query_table in datacut_query_table_model.objects.filter(schema="dit").all():
        query_table.schema = "dbt"
        query_table.save()


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0163_copy_dit_source_table_dbt"),
    ]

    operations = [
        migrations.RunPython(migrate_schema_dit_dbt, reverse_code=migrations.RunPython.noop),
    ]
