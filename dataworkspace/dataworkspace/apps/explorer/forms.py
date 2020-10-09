from django.conf import settings
from django.forms import CharField, Field, ModelForm, ValidationError
from django.forms.widgets import Select

from dataworkspace.apps.explorer.models import Query


class SqlField(Field):
    def validate(self, value):
        query = value.strip().upper()
        if not any([query.startswith("SELECT"), query.startswith("WITH")]):
            raise ValidationError(
                "Enter a SQL statement starting with SELECT or WITH", code="InvalidSql"
            )


class QueryForm(ModelForm):

    sql = SqlField()
    connection = CharField(widget=Select, required=False)
    title = CharField(
        error_messages={
            'required': 'Enter a title for the query',
            'max_length': 'The title for the query must be 255 characters or fewer',
        }
    )

    def __init__(self, *args, **kwargs):
        super(QueryForm, self).__init__(*args, **kwargs)
        self.fields['connection'].widget.choices = self.connections
        if not self.instance.connection:
            self.initial['connection'] = settings.EXPLORER_DEFAULT_CONNECTION
        self.fields['connection'].widget.attrs['class'] = 'form-control'

    def clean(self):
        if self.instance and self.data.get('created_by_user', None):
            self.cleaned_data['created_by_user'] = self.instance.created_by_user
        return super(QueryForm, self).clean()

    @property
    def created_by_user_email(self):
        return (
            self.instance.created_by_user.email
            if self.instance.created_by_user
            else '--'
        )

    @property
    def created_at_time(self):
        return self.instance.created_at.strftime('%Y-%m-%d')

    @property
    def connections(self):
        return [(v, k) for k, v in settings.EXPLORER_CONNECTIONS.items()]

    class Meta:
        model = Query
        fields = ['title', 'sql', 'description', 'connection']
