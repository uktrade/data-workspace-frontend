import pglast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import connections
from django.forms import ChoiceField, widgets

from dataworkspace.apps.datasets.constants import PipelineType
from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
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
        except pglast.parser.ParseError as e:  # pylint: disable=c-extension-no-member
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
        choices=(
            ("sql", "SQL Pipeline"),
            ("sharepoint", "Sharepoint Pipeline"),
        ),
    )
