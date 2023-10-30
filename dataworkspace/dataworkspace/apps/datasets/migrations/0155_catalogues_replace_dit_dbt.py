import re
from django.db import migrations


def search_and_replace_model(model):
    skip_items = [
        'great.gov.uk value for money survey responses',
        'DDaT Recruitment Survey', 'Regional inbound enquiries 2018-2020',
        'DDaT Return to the office survey', 'DIT MS Teams feedback survey',
        'Civil Service Leadership Academy Training Records',
        'Jobs supported by UK exports',
        'DIT staff and contractors: leavers',
        'HR People Data merged 13 month rolling',
        'People Data: Cyber team report',
        'DIT staff and contractors: leavers',
        'DIT people data: joiners and leavers',
        'DIT Return to office: Personal Risk Assessment (PRA) data'
    ]
    
    for dataset in model.objects.all():
        if dataset.name in skip_items:
            continue
        dataset.name = re.sub(dataset.name, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.name = re.sub(dataset.name, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.short_description = re.sub(dataset.short_description, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.short_description = re.sub(dataset.short_description, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.description = re.sub(dataset.description, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.description = re.sub(dataset.description, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.retention_policy = re.sub(dataset.retention_policy, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.retention_policy = re.sub(dataset.retention_policy, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.personal_data = re.sub(dataset.personal_data, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.personal_data = re.sub(dataset.personal_data, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.license = re.sub(dataset.license, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.license = re.sub(dataset.license, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)

        dataset.restrictions_on_usage = re.sub(dataset.restrictions_on_usage, "DIT", "DBT", flags=re.IGNORECASE)
        dataset.restrictions_on_usage = re.sub(dataset.restrictions_on_usage, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)
        
        eligibility_criteria = list(dataset.eligibility_criteria.all())
        eligibility_criteria = [
            re.sub(criteria, "DIT", "DBT", flags=re.IGNORECASE)
            for criteria in eligibility_criteria
        ]
        eligibility_criteria = [
            re.sub(criteria, "Department of International Trade", "Department for Business and Trade", flags=re.IGNORECASE)
            for criteria in eligibility_criteria
        ]

def search_and_replace_catalogue_items(apps, _):
    model = apps.get_model("datasets", "app_dataset").objects.all()
    search_and_replace_model(model)

    model = apps.get_model("datasets", "datasets_visualisationcatalogueitem").objects.all()
    search_and_replace_model(model)

    model = apps.get_model("datasets", "app_referencedataset").objects.all()
    search_and_replace_model(model)

class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0154_vis_dataset_m2m_seq"),
    ]

    operations = [
        migrations.RunPython(
            search_and_replace_catalogue_items, reverse_code=migrations.RunPython.noop
        ),
    ]
