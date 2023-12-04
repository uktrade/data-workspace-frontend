from django.db import migrations
from django.db.models import F, Func, Value


def replace_func(field_name, find_str, replace_str):
    return Func(F(field_name), Value(find_str), Value(replace_str), function="replace")


def move_schema_dit_dbt(apps, _):
    source_table = apps.get_model("datasets", "SourceTable")
    source_table.objects.filter(schema="dit").update(schema="dbt")

    data_cut = apps.get_model("datasets", "CustomDatasetQuery")
    data_cut.objects.update(name=replace_func("query", "dit.", "dbt."))


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0158_alter_pipeline_schedule"),
    ]

    operations = [
        migrations.RunPython(move_schema_dit_dbt, reverse_code=migrations.RunPython.noop),
    ]
