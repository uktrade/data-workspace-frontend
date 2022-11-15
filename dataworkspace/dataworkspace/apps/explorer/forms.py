from django.conf import settings
from django.contrib.auth import get_user_model
from django.forms import CharField, Field, ModelForm, ValidationError
from django.forms.widgets import HiddenInput, Select

from pglast import parser

from dataworkspace.apps.explorer.models import Query
from dataworkspace.forms import (
    GOVUKDesignSystemBooleanField,
    GOVUKDesignSystemEmailValidationModelChoiceField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
)


class SqlField(Field):
    def validate(self, value):
        query = value.strip()
        try:
            # parse nodes are callable, to serialize it into dictionaries
            sql = parser.parse_sql(query)[0]()
        except IndexError as ex:
            raise ValidationError(
                "Enter a SQL statement starting with SELECT, WITH or EXPLAIN",
                code="InvalidSql",
            ) from ex
        except parser.ParseError as ex:  # pylint: disable=c-extension-no-member
            raise ValidationError(f"Invalid SQL: {ex}", code="InvalidSql") from ex

        stmt = sql["stmt"]["@"]
        if stmt == "ExplainStmt":
            stmt = sql["stmt"]["query"]["@"]
        if stmt != "SelectStmt":
            raise ValidationError(
                "Enter a SQL statement starting with SELECT, WITH or EXPLAIN",
                code="InvalidSql",
            )


class QueryForm(ModelForm):

    sql = SqlField()
    connection = CharField(widget=Select, required=False)
    title = CharField(
        error_messages={
            "required": "Enter a title for the query",
            "max_length": "The title for the query must be 255 characters or fewer",
        }
    )

    def __init__(self, *args, **kwargs):
        # pylint: disable=super-with-arguments
        super(QueryForm, self).__init__(*args, **kwargs)
        self.fields["connection"].widget.choices = self.connections
        if not self.instance.connection:
            self.initial["connection"] = settings.EXPLORER_DEFAULT_CONNECTION
        self.fields["connection"].widget.attrs["class"] = "form-control"

    def clean(self):
        if self.instance and self.data.get("created_by_user", None):
            self.cleaned_data["created_by_user"] = self.instance.created_by_user
        # pylint: disable=super-with-arguments
        return super(QueryForm, self).clean()

    @property
    def created_by_user_email(self):
        return self.instance.created_by_user.email if self.instance.created_by_user else "--"

    @property
    def created_at_time(self):
        return self.instance.created_at.strftime("%Y-%m-%d")

    @property
    def connections(self):
        return [(v, k) for k, v in settings.EXPLORER_CONNECTIONS.items()]

    class Meta:
        model = Query
        fields = ["title", "sql", "description", "connection"]


class ShareQueryForm(GOVUKDesignSystemForm):
    to_user = GOVUKDesignSystemEmailValidationModelChoiceField(
        label="Who would you like to share the query with?",
        help_text="Recipient's email",
        queryset=get_user_model().objects.all(),
        to_field_name="email",
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False),
        required=True,
        error_messages={
            "invalid_email": "Enter the email address in the correct format, for example name@digital.trade.gov.uk",
            "invalid_choice": "The user you are sharing with must have a DIT staff SSO account",
        },
    )
    message = GOVUKDesignSystemTextareaField(
        label="Message",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 20},
        ),
    )
    query = CharField(required=True, widget=HiddenInput())
    copy_sender = GOVUKDesignSystemBooleanField(
        label="Send me a copy of the email",
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        if len(cleaned_data["query"]) > 1950:
            raise ValidationError(
                f"The character length of your query ({len(cleaned_data['query'])} characters), "
                "is longer than the current shared query length limit (1950 characters).",
                code="SQLTooLong",
            )
        return cleaned_data
