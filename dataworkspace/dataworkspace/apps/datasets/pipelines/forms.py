import pglast

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import connections
from django.forms import ChoiceField, widgets

from dataworkspace.apps.datasets.constants import PipelineType, PipelineRefreshType
from dataworkspace.apps.datasets.models import Pipeline, DataCutDataset
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemSelectWidget,
)


def validate_schema_and_table(value):
    try:
        schema, table = value.split(".")
    except ValueError as ex:
        raise ValidationError("Table name must be in the format <schema>.<table name>") from ex
    if len(schema) > 63:
        raise ValidationError("Schema name must be less than 63 characters")
    if len(table) > 42:
        raise ValidationError("Table name must be less than 42 characters")


class BasePipelineCreateForm(GOVUKDesignSystemModelForm):
    pipeline_type = None
    type = ChoiceField(
        choices=PipelineType.choices,
        widget=widgets.HiddenInput(),
    )
    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into",
        help_text="This cannot be changed later",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a table name."},
        validators=(
            RegexValidator(
                message="Table name must be in the format <schema>.<table name>",
                regex=r"^[a-zA-Z_][a-zA-Z0-9_]*.[a-zA-Z_][a-zA-Z0-9_]*$",
            ),
            validate_schema_and_table,
        ),
    )

    class Meta:
        model = Pipeline
        fields = ["table_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["type"] = self.pipeline_type.value


class SQLPipelineCreateForm(BasePipelineCreateForm):
    pipeline_type = PipelineType.SQL
    sql = GOVUKDesignSystemTextareaField(
        label="SQL Query",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter an SQL query."},
    )

    class Meta:
        model = Pipeline
        fields = ["table_name", "sql", "type"]

    def save(self, commit=True):
        pipeline = super().save(commit=False)
        pipeline.config = {"sql": self.cleaned_data["sql"]}
        if commit:
            pipeline.save()
        return pipeline

    def clean_sql(self):
        query = self.cleaned_data["sql"].strip().rstrip(";")
        try:
            statements = pglast.parse_sql(query)
        except pglast.parser.ParseError as e:
            raise ValidationError(e) from e
        else:
            if len(statements) > 1:
                raise ValidationError("Enter a single statement")
            statement_dict = statements[0].stmt()
            if statement_dict["@"] != "SelectStmt":
                raise ValidationError("Only SELECT statements are supported")

        # Check that the query runs
        with connections[list(settings.DATABASES_DATA.items())[0][0]].cursor() as cursor:
            try:
                cursor.execute(f"SELECT * FROM ({query}) sq LIMIT 0")
            except Exception as e:  # pylint: disable=broad-except
                raise ValidationError(
                    "Error running query. Please check the query runs successfully before saving."
                ) from e

        columns = [x.name for x in cursor.description if x.name is not None]
        if len(set(columns)) != len(columns):
            raise ValidationError("Duplicate column names found")

        return self.cleaned_data["sql"]


class SQLPipelineEditForm(SQLPipelineCreateForm):
    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        disabled=True,
    )


class SharepointPipelineCreateForm(BasePipelineCreateForm):
    pipeline_type = PipelineType.SHAREPOINT
    site_name = GOVUKDesignSystemCharField(
        label="The site name that the sharepoint list is published under",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a valid site name."},
    )
    list_name = GOVUKDesignSystemCharField(
        label="The name of the sharepoint list",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a valid list name."},
    )

    class Meta:
        model = Pipeline
        fields = ["table_name", "site_name", "list_name", "type"]

    def save(self, commit=True):
        pipeline = super().save(commit=False)
        pipeline.config = {
            "site_name": self.cleaned_data["site_name"],
            "list_name": self.cleaned_data["list_name"],
        }
        if commit:
            pipeline.save()
        return pipeline


class ScheduledReportPipelineCreateForm(SQLPipelineCreateForm):
    pipeline_type = PipelineType.SCHEDULED_REPORT
    table_name = GOVUKDesignSystemCharField(
        label="Name for the report",
        help_text=(
            "This is the name of the download link on the data cut page. "
            "The report's run date will be appended."
        ),
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a name for the report."},
        validators=[],
    )
    base_file_name = GOVUKDesignSystemCharField(
        label="Base name for the downloaded CSV file",
        help_text="The downloaded file name will include the base file name and the run date, "
        "e.g. <base-file-name>-yyyy-mm-dd.csv",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a base name for the CSV file."},
        validators=(
            RegexValidator(
                message="Base file name can only contain alphanumeric characters hyphens and underscores",
                regex=r"^[a-zA-Z_][a-zA-Z0-9_-]*$",
            ),
        ),
    )
    sql = GOVUKDesignSystemTextareaField(
        label="SQL Query",
        help_text="Enter your SQL. To make use the the run date of the pipeline insert {{run_date}}",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter an SQL query."},
    )
    day_of_month = GOVUKDesignSystemChoiceField(
        label="Day of month to run the report",
        help_text="Pipeline will start at midnight but will wait for any dependent pipelines to run first",
        choices=[(str(x), ordinal(x)) for x in range(1, 32)] + [("L", "Last day")],
        widget=GOVUKDesignSystemSelectWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
        ),
    )
    refresh_type = GOVUKDesignSystemRadioField(
        label="When to refresh the report",
        initial=PipelineRefreshType.NEVER,
        choices=PipelineRefreshType.choices,
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", label_size="s", small=True),
    )
    dataset = GOVUKDesignSystemChoiceField(
        label="Data cut to add the report to",
        help_text="On pipeline completion, the report will be automatically added to this dataset.",
        required=False,
        widget=GOVUKDesignSystemSelectWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
        ),
    )

    class Meta:
        model = Pipeline
        fields = [
            "table_name",
            "base_file_name",
            "type",
            "sql",
            "day_of_month",
            "refresh_type",
            "dataset",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].choices = [("", "-")] + [
            (str(x.id), x.name) for x in DataCutDataset.objects.live()
        ]

    def save(self, commit=True):
        pipeline = super().save(commit=False)
        pipeline.config = {
            "sql": self.cleaned_data["sql"],
            "day_of_month": self.cleaned_data["day_of_month"],
            "refresh_type": self.cleaned_data["refresh_type"],
            "dataset": self.cleaned_data["dataset"],
            "base_file_name": self.cleaned_data["base_file_name"],
            "schedule": self.cleaned_data["day_of_month"],
        }
        if commit:
            pipeline.save()
        return pipeline


class ScheduledReportPipelineEditForm(ScheduledReportPipelineCreateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        disabled_fields = ["table_name", "base_file_name", "day_of_month", "refresh_type"]
        for field in disabled_fields:
            self.fields[field].disabled = True


class SharepointPipelineEditForm(SharepointPipelineCreateForm):
    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        disabled=True,
    )


class PipelineTypeForm(GOVUKDesignSystemForm):
    pipeline_type = GOVUKDesignSystemRadioField(
        required=True,
        label="Select the type of pipeline you would like to create",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
        choices=PipelineType.choices,
    )
