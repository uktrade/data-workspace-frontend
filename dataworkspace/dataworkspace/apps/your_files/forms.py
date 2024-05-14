import waffle
from botocore.exceptions import ClientError
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MaxLengthValidator

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.forms import ConditionalSupportTypeRadioWidget
from dataworkspace.apps.core.utils import (
    get_all_schemas,
    get_postgres_datatype_choices,
    get_user_s3_prefixes,
    table_exists,
)
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemSelectWidget,
)
from dataworkspace.apps.core.utils import get_team_schemas_for_user
from dataworkspace.apps.your_files.utils import get_schema_for_user


class CreateTableForm(GOVUKDesignSystemForm):
    path = forms.CharField(required=True, widget=forms.HiddenInput())
    schema = forms.CharField(required=True, widget=forms.HiddenInput())
    table_name = GOVUKDesignSystemCharField(
        label="How do you want to name your table?",
        help_text="This will be the name you will see your table with, in your personal database schema.",
        required=True,
        widget=GOVUKDesignSystemTextWidget(label_size="xl", label_is_heading=True),
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z][a-zA-Z0-9_]*$",
                message="Table names can contain only letters, numbers and underscores",
                code="invalid-table-name",
            ),
            MaxLengthValidator(
                42, message="Table names must be no longer than 42 characters long"
            ),
        ],
    )
    force_overwrite = forms.BooleanField(required=False, widget=forms.HiddenInput())
    table_exists_action = GOVUKDesignSystemChoiceField(
        required=False,
        choices=(
            ("overwrite", "Overwrite the existing table"),
            ("append", "Append records to the existing table"),
        ),
        label="Action to take",
        widget=GOVUKDesignSystemSelectWidget(label_is_heading=False),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        if self.initial.get("force_overwrite"):
            self.fields["table_name"].widget = forms.HiddenInput()

    def clean_path(self):
        path = self.cleaned_data["path"]
        client = get_s3_client()

        paths = get_user_s3_prefixes(self.user).values()

        has_permissions = any(path.startswith(_path) for _path in paths)

        if not has_permissions:
            raise ValidationError("You don't have permission to access this file")

        if not path.endswith(".csv"):
            raise ValidationError("Invalid file type. Only CSV files are currently supported")

        try:
            client.head_object(Bucket=settings.NOTEBOOKS_BUCKET, Key=path)
        except ClientError:
            # pylint: disable=raise-missing-from
            raise ValidationError("This file does not exist in S3")

        return path

    def clean(self):
        # If incremental import support is enabled and the table already exists, prompt the user
        # to determine if they want to overwrite or append to the existing table
        table_name = self.cleaned_data.get("table_name")
        if waffle.switch_is_active(settings.INCREMENTAL_S3_IMPORT_PIPELINE_FLAG) and table_name:
            if (
                table_exists(
                    settings.EXPLORER_DEFAULT_CONNECTION, self.cleaned_data["schema"], table_name
                )
                and not self.cleaned_data.get("force_overwrite")
                and not self.cleaned_data.get("table_exists_action")
            ):
                self.add_error(
                    "table_name",
                    ValidationError("This table already exists", code="duplicate-table"),
                )

        return super().clean()


class CreateTableSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemRadioField(
        label="In which schema would you like your table?",
        widget=GOVUKDesignSystemRadiosWidget,
        error_messages={"required": "You must select a schema."},
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        if self.user.is_staff:
            all_schemas = get_all_schemas()
            all_choices = [(schema, schema) for schema in all_schemas] + [
                ("new", "None of the above - Create new schema")
            ]
        else:
            all_choices = []

        user_schema = get_schema_for_user(self.user)
        user_choice = [("user", f"{user_schema} (your private schema)")]

        team_schemas = get_team_schemas_for_user(self.user)
        team_choices = [
            (
                team_schema["name"],
                f"{team_schema['schema_name']} ({team_schema['name']} shared schema)",
            )
            for team_schema in team_schemas
        ]
        schema_choices = user_choice + team_choices + all_choices
        self.fields["schema"].choices = schema_choices


class CreateSchemaForm(GOVUKDesignSystemForm):
    schema = GOVUKDesignSystemCharField(
        label="What would you like to name your schema?",
        widget=GOVUKDesignSystemTextWidget,
        error_messages={"required": "You must enter a word."},
    )


class CreateTableDataTypesForm(CreateTableForm):
    auto_generate_id_column = GOVUKDesignSystemRadioField(
        label="Do you want to generate an ID column?",
        help_text="This will add an ID column and assign an ID to each row in your table. \
        The ID will be an increasing integer, e.g. 1, 2, 3.",
        choices=[("True", "Yes"), ("False", "No")],
        widget=ConditionalSupportTypeRadioWidget(heading="h2", label_size="m", small=False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.column_definitions = kwargs.pop("column_definitions")
        self.show_id_form = True
        if not self.column_definitions:
            raise ValueError("Definitions for at least one column must be provided")
        super().__init__(*args, **kwargs)
        self.fields["table_exists_action"].widget = forms.HiddenInput()

        for col_def in self.column_definitions:
            if col_def["column_name"] == "id":
                self.show_id_form = False
            self.fields[col_def["column_name"]] = GOVUKDesignSystemChoiceField(
                label=col_def["column_name"],
                initial=col_def["data_type"],
                choices=get_postgres_datatype_choices(),
                widget=GOVUKDesignSystemSelectWidget(
                    label_is_heading=False,
                    extra_label_classes="govuk-visually-hidden",
                ),
            )

    def get_data_type_fields(self):
        for col_def in self.column_definitions:
            yield self[col_def["column_name"]], ", ".join(map(str, col_def["sample_data"]))
