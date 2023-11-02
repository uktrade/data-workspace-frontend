import re
from django.db import migrations
from django.db.models import F, Func, Value

skip_items = [
    "great.gov.uk value for money survey responses",
    "DDaT Recruitment Survey",
    "Regional inbound enquiries 2018-2020",
    "DDaT Return to the office survey",
    "DIT MS Teams feedback survey",
    "Civil Service Leadership Academy Training Records",
    "Jobs supported by UK exports",
    "DIT staff and contractors: leavers",
    "HR People Data merged 13 month rolling",
    "People Data: Cyber team report",
    "DIT staff and contractors: leavers",
    "DIT people data: joiners and leavers",
    "DIT Return to office: Personal Risk Assessment (PRA) data",
]
dit = "DIT"
dbt = "DBT"
dit_full = "Department for International Trade"
dbt_full = "Department for Business and Trade"
dit_full_low = "department for international trade"


def replace_func(field_name, find_str, replace_str):
    return Func(F(field_name), Value(find_str), Value(replace_str), function="replace")


def search_and_replace_all_fields(model):
    model.objects.exclude(name__in=skip_items).update(
        name=replace_func("name", dit, dbt),
        short_description=replace_func("short_description", dit, dbt),
        description=replace_func("description", dit, dbt),
        licence=replace_func("licence", dit, dbt),
        restrictions_on_usage=replace_func("restrictions_on_usage", dit, dbt),
    )
    model.objects.exclude(name__in=skip_items).update(
        name=replace_func("name", dit_full, dbt_full),
        short_description=replace_func("short_description", dit_full, dbt_full),
        description=replace_func("description", dit_full, dbt_full),
        licence=replace_func("licence", dit_full, dbt_full),
        restrictions_on_usage=replace_func("restrictions_on_usage", dit_full, dbt_full),
    )
    model.objects.exclude(name__in=skip_items).update(
        name=replace_func("name", dit_full_low, dbt_full),
        short_description=replace_func("short_description", dit_full_low, dbt_full),
        description=replace_func("description", dit_full_low, dbt_full),
        licence=replace_func("licence", dit_full_low, dbt_full),
        restrictions_on_usage=replace_func("restrictions_on_usage", dit_full_low, dbt_full),
    )


def search_and_replace_specific_fields(model):
    model.objects.exclude(name__in=skip_items).update(
        retention_policy=replace_func("retention_policy", dit, dbt),
        personal_data=replace_func("personal_data", dit, dbt),
    )
    model.objects.exclude(name__in=skip_items).update(
        retention_policy=replace_func("retention_policy", dit_full, dbt_full),
        personal_data=replace_func("personal_data", dit_full, dbt_full),
    )
    model.objects.exclude(name__in=skip_items).update(
        retention_policy=replace_func("retention_policy", dit_full_low, dbt_full),
        personal_data=replace_func("personal_data", dit_full_low, dbt_full),
    )
    for dataset in model.objects.exclude(name__in=skip_items).all():
        if dataset.eligibility_criteria:
            eligibility_criteria = [
                re.sub(criteria, dit, dbt, flags=re.IGNORECASE)
                for criteria in list(dataset.eligibility_criteria)
            ]
            dataset.eligibility_criteria = eligibility_criteria
            dataset.save()
            eligibility_criteria = [
                re.sub(
                    criteria,
                    dit_full,
                    dbt_full,
                    flags=re.IGNORECASE,
                )
                for criteria in list(dataset.eligibility_criteria)
            ]
            dataset.eligibility_criteria = eligibility_criteria
            dataset.save()


def search_and_replace_catalogue_items(apps, _):
    model = apps.get_model("datasets", "DataSet")
    search_and_replace_all_fields(model)
    search_and_replace_specific_fields(model)

    model = apps.get_model("datasets", "VisualisationCatalogueItem")
    search_and_replace_all_fields(model)
    search_and_replace_specific_fields(model)

    model = apps.get_model("datasets", "ReferenceDataset")
    search_and_replace_all_fields(model)


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0154_vis_dataset_m2m_seq"),
    ]

    operations = [
        migrations.RunPython(
            search_and_replace_catalogue_items, reverse_code=migrations.RunPython.noop
        ),
    ]
