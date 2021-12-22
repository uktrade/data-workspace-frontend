from django import forms

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget
)


class PipelineCreateForm(forms.ModelForm):
    class Meta:
        model = Pipeline
        fields = ['table_name', 'sql_query']

    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into. This cannot be changed later",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a table name."},
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


class PipelineEditForm(forms.ModelForm):
    class Meta:
        model = Pipeline
        fields = ['sql_query']

    table_name = GOVUKDesignSystemCharField(
        label="Schema and table name the pipeline ingests into. This cannot be changed later",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "Enter a table name."},
        required=False
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
