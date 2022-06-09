from datetime import datetime, timedelta
from django.utils.text import slugify

from dataworkspace.apps.core.models import Database
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import MasterDataset, SourceTable

from ._tags import get_dev_source_tag, get_example_topic_tag, get_superset_tag

open_datasets = [
    {
        "name": "Coronavirus (COVID-19) in the UK",
        "short_description": "UK government data on COVID-19 prevalence in the UK, including daily updated figures for cases and deaths by various geographical areas.",
        "description": '<div>Official UK government data for COVID-19&nbsp;cases and deaths in the UK.</div><div>&nbsp;</div><div>It is taken from the <a href="https://coronavirus.data.gov.uk/">GOV.UK COVID-19 Dashboard</a>&nbsp;and is updated on a daily basis. For full information, see the <a href="https://coronavirus.data.gov.uk/details/about-data" target="_blank">published guidance on the data here</a>.</div><div>&nbsp;</div><div>There are three tables available, all of which show daily COVID-19 cases and deaths for various geographical areas:</div><ul>	<li><strong>COVID-19 cases by nation</strong> - shows data for each of the UK nations (England, Northern Ireland, Scotland and&nbsp;Wales)</li>	<li><strong>COVID-19 cases by region</strong> - shows data for the 9 English regions, as listed in the UK regions and nations reference dataset&nbsp;</li>	<li><strong>COVID-19&nbsp;cases by local authority</strong> - shows data for each lower-tier local authority in the UK, as shown in the&nbsp;Local Authority Districts reference dataset</li></ul>',
        "source_tables": [
            {
                "database": "datasets",
                "schema": "public_health_england",
                "table": "uk_covid_prevalence_data_by_ltla",
            },
            {
                "database": "datasets",
                "schema": "public_health_england",
                "table": "uk_covid_prevalence_data_by_nation",
            },
            {
                "database": "datasets",
                "schema": "public_health_england",
                "table": "uk_covid_prevalence_data_by_region",
            },
        ],
    },
    {
        "name": "Gender pay gap data for UK employers",
        "short_description": "This dataset contains gender pay gap data for UK companies with 250 or more employees, as published by the UK Cabinet Office.",
        "description": '<div>This data is an open dataset collected and published by the UK Cabinet Office.<br><br>Using this service, all UK employers are able to report the pay gap between men and women in their company. This is mandatory for companies with 250 or more employees.<br><br>For more information visit the <a href="https://gender-pay-gap.service.gov.uk/" target="_blank">Gender Pay Gap service on gov.uk</a>.</div>',
        "source_tables": [
            {
                "database": "datasets",
                "schema": "cabinet_office",
                "table": "gender_pay_gap",
            }
        ],
    },
    {
        "name": "GDACS global disaster data",
        "short_description": "This dataset contains geographical risk information on natural disasters held by GDACS.",
        "description": '<div>This dataset contains geographical risk information on natural disasters held by the Global Disaster Alert and Coordination System (GDACS). This includes the most recent geographical alerts for events categorised as orange and red in the previous 12 months.</div>  <div>&nbsp;</div>  <div>This data has been collected by GDACS to facilitate international exchange and decision making, and the dataset will be used by the Global Supply Chains teams for the purposes of coordinating geographical risk information.&nbsp;</div>  <div>&nbsp;</div>  <h2>About GDACS&nbsp;</h2>  <div><a href="https://www.gdacs.org/">The Global Disaster Alert and Coordination System (GDACS)</a> is a cooperation framework between the United Nations, the European Commission and disaster managers worldwide to improve alerts, information exchange and coordination in the first phase after major sudden-onset disasters.&nbsp;&nbsp;The objective of GDACS is to assess the overall impact of natural hazards on affected countries.</div>  <div>&nbsp;</div>  <div>GDACS alert levels aim at drawing attention to events&nbsp;that might turn out to be serious enough to require international intervention, or, that could overwhelm national authorities\' response capacity.&nbsp;GDCAS alerts are issued&nbsp;for earthquakes and possibly subsequent tsunamis, tropical cyclones, floods and volcanoes.</div>  <div>&nbsp;</div>  <div>The selection and alert level of natural hazards in GDACS is based on automatic impact assessment models, without human intervention. Information about the location, strength and other characteristics is then used to calculate&nbsp;the affected area and the expected impact. Detailed information on how these levels are calculated for various events can be found <a href="https://www.gdacs.org/Knowledge/overview.aspx">here</a>.&nbsp;</div>  <h2>How to use this Data&nbsp;</h2>  <div>There is one table available: major_events.<br> <br> This dataset is an open dataset collected and published by&nbsp;GDACS.&nbsp;</div> ',
        "source_tables": [{"database": "datasets", "schema": "gdacs", "table": "major_events"}],
    },
    {
        "name": "COVID-19 Johns Hopkins University data",
        "short_description": "This dataset contains the data underlying the John Hopkins University COVID-19 Dashboard.",
        "description": '<div> <div> <p>Analyse in&nbsp;our&nbsp;<a href="https://data.trade.gov.uk/tools/" rel="noreferrer noopener" target="_blank">tools</a>&nbsp;the data&nbsp;shown in&nbsp;the&nbsp;<a href="https://coronavirus.jhu.edu/map.html" rel="noreferrer noopener" target="_blank">COVID-19 global data dashboard</a>&nbsp;operated by the Johns Hopkins University Centre for Systems Science and Engineering.&nbsp;</p> </div>  <div> <p>Find international comparisons of COVID-19 cases, deaths and recoveries. Also&nbsp;<a href="https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data" rel="noreferrer noopener" target="_blank">more information</a>&nbsp;including corrections and modifications.&nbsp;</p> </div>  <div> <p>Supported by the ESRI Living Atlas Team and the Johns Hopkins University Applied Physics Lab.&nbsp;</p> </div>  <div> <p>This data is&nbsp;updated daily.&nbsp;</p> </div>  <div> <p>The data by country is&nbsp;available to&nbsp;<a href="https://data.trade.gov.uk/datasets/5fc9b423-a4d8-488c-9409-d8d7f596d1ba#covid-19-johns-hopkins-university-global-datacut" rel="noreferrer noopener" target="_blank">download</a></p> </div> </div>',
        "source_tables": [
            {
                "database": "datasets",
                "schema": "public",
                "table": "csse_covid19_time_series_global",
            }
        ],
    },
]

master_datasets = [
    {
        "name": "Trivial Example",
        "short_description": "A trivial dataset based on the DIT readme example",
        "description": '<div>A trivially simple dataset based on the example airflow DAG from DIT <a href="#">developer manual</a></div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>\r\n\r\n<div>&nbsp;</div>',
        "source_tables": [{"database": "datasets", "schema": "example", "table": "local__spoons"}],
    },
    {
        "name": "Superset Video Game Sales",
        "is_superset": True,
        "short_description": "A dataset of video game sales",
        "description": "A dataset of video game sales taken from superset example data",
        "source_tables": [
            {
                "database": "datasets",
                "schema": "example",
                "table": "superset__video_game_sales",
            },
        ],
    },
    {
        "name": "Superset Sales Data",
        "is_superset": True,
        "short_description": "A dataset of sales data",
        "description": "A dataset of sales data taken from superset example data",
        "source_tables": [
            {"database": "datasets", "schema": "example", "table": "superset__sales"}
        ],
    },
    {
        "name": "Superset Unicode Test",
        "is_superset": True,
        "short_description": "A dataset of unicode test data",
        "description": "A dataset of unicode test data taken from superset example data",
        "source_tables": [
            {
                "database": "datasets",
                "schema": "example",
                "table": "superset__unicode_test",
            }
        ],
    },
    {
        "name": "Superset Flights Test",
        "is_superset": True,
        "short_description": "A dataset of unicode test data",
        "description": "A dataset of unicode test data taken from superset example data",
        "source_tables": [
            {"database": "datasets", "schema": "example", "table": "superset__flights"}
        ],
    },
]


def create_opendata_datasets(iam_user, iao_user, stdout):
    for dataset in open_datasets:
        dataset["restrictons_on_usage"] = "No restrictions - this is an open dataset"

    return _create_datasets(iam_user, iao_user, open_datasets, "OPEN", stdout)


def create_example_datasets(iam_user, iao_user, stdout):
    for dataset in master_datasets:
        dataset["restrictons_on_usage"] = "No restrictions - this is example data"
    return _create_datasets(iam_user, iao_user, master_datasets, "REQUIRES_AUTHORIZATION", stdout)


def _create_datasets(iam_user, iao_user, datasets, access_type, stdout):

    published_date = datetime.today()

    for dataset in datasets:
        catalogue_item, created = MasterDataset.objects.get_or_create(
            name=dataset["name"],
            defaults={
                "type": DataSetType.MASTER,
                "slug": slugify(dataset["name"]),
                "user_access_type": access_type,
                "published": True,
            },
        )

        stdout.write(
            "MasterDataset %s was %s" % (dataset["name"], "created" if created else "updated")
        )

        catalogue_item.users_access_type = access_type
        catalogue_item.information_asset_manager = iam_user
        catalogue_item.information_asset_owner = iao_user
        catalogue_item.short_description = dataset["short_description"]
        catalogue_item.description = dataset["description"]
        catalogue_item.tags.add(get_dev_source_tag())
        catalogue_item.tags.add(get_example_topic_tag())
        catalogue_item.published_at = published_date

        # adjust published date to influence the sort order
        published_date = published_date - timedelta(days=13)

        catalogue_item.restrictions_on_usage = dataset.get("restrictons_on_usage", "")

        if dataset.get("is_superset"):
            catalogue_item.tags.add(get_superset_tag())

        catalogue_item.save()

        for source in dataset["source_tables"]:
            database = Database.objects.get(memorable_name=source["database"])

            table, created = SourceTable.objects.get_or_create(
                database=database,
                schema=source["schema"],
                table=source["table"],
                dataset=catalogue_item,
                defaults={"name": dataset["name"]},
            )

            stdout.write(
                "  SourceTable %s was %s" % (source["table"], "created" if created else "updated")
            )
