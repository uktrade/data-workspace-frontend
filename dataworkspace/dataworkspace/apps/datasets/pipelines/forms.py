import psqlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import connections

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemModelForm,
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


class PipelineCreateForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = Pipeline
        fields = ["table_name", "sql_query"]

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
    sql_query = GOVUKDesignSystemTextareaField(
        label="SQL Query",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter an SQL query."},
    )

    def clean_sql_query(self):
        try:
            statements = psqlparse.parse(self.cleaned_data["sql_query"])
        except psqlparse.exceptions.PSqlParseError as e:
            raise ValidationError(e) from e
        else:
            if len(statements) > 1:
                raise ValidationError("Enter a single statement")
            if isinstance(statements[0], dict):
                if "CreateStmt" in statements[0]:
                    raise ValidationError("CREATE statements are not supported")
                if "DropStmt" in statements[0]:
                    raise ValidationError("DROP statements are not supported")
            columns = [t.name for t in statements[0].target_list]
            if len(columns) != len(set(columns)):
                raise ValidationError("Duplicate column names found")

        # Check that the query runs
        with connections[list(settings.DATABASES_DATA.items())[0][0]].cursor() as cursor:
            try:
                cursor.execute(f"SELECT * FROM ({self.cleaned_data['sql_query']}) sq LIMIT 0")
            except Exception as e:  # pylint: disable=broad-except
                raise ValidationError(
                    "Error running query. Please check the query runs successfully before saving."
                ) from e

        return self.cleaned_data["sql_query"]


class PipelineEditForm(PipelineCreateForm):
    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        disabled=True,
    )
