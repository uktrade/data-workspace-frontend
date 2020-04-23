from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.forms import Textarea, TextInput, ModelChoiceField, HiddenInput

from dataworkspace.apps.applications.models import VisualisationApproval
from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
from dataworkspace.forms import GOVUKDesignSystemModelForm


class _NiceEmailValidationModelChoiceField(ModelChoiceField):
    def clean(self, value):
        if value:
            EmailValidator(message=self.error_messages['invalid_email'])(value)
        return super().clean(value)


class VisualisationsUICatalogueItemForm(GOVUKDesignSystemModelForm):
    enquiries_contact = _NiceEmailValidationModelChoiceField(
        queryset=get_user_model().objects.all(),
        to_field_name='email',
        widget=TextInput,
        required=False,
        error_messages={
            "invalid_email": "Enter a valid email address for the enquiries contact",
            "invalid_choice": "The enquiries contact must have previously visited Data Workspace",
        },
    )
    secondary_enquiries_contact = _NiceEmailValidationModelChoiceField(
        queryset=get_user_model().objects.all(),
        to_field_name='email',
        widget=TextInput,
        required=False,
        error_messages={
            "invalid_email": "Enter a valid email address for the secondary enquiries contact",
            "invalid_choice": "The secondary enquiries contact must have previously visited Data Workspace",
        },
    )
    information_asset_manager = _NiceEmailValidationModelChoiceField(
        queryset=get_user_model().objects.all(),
        to_field_name='email',
        widget=TextInput,
        required=False,
        error_messages={
            "invalid_email": "Enter a valid email address for the information asset manager",
            "invalid_choice": "The information asset manager must have previously visited Data Workspace",
        },
    )
    information_asset_owner = _NiceEmailValidationModelChoiceField(
        queryset=get_user_model().objects.all(),
        to_field_name='email',
        widget=TextInput,
        required=False,
        error_messages={
            "invalid_email": "Enter a valid email address for the information asset owner",
            "invalid_choice": "The information asset owner must have previously visited Data Workspace",
        },
    )

    class Meta:
        model = VisualisationCatalogueItem
        fields = [
            'short_description',
            'description',
            'enquiries_contact',
            'secondary_enquiries_contact',
            'information_asset_manager',
            'information_asset_owner',
            'licence',
            'retention_policy',
            'personal_data',
            'restrictions_on_usage',
        ]
        widgets = {"retention_policy": Textarea, "restrictions_on_usage": Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['short_description'].error_messages[
            'required'
        ] = "The visualisation must have a summary"

        self._email_fields = [
            'enquiries_contact',
            'secondary_enquiries_contact',
            'information_asset_manager',
            'information_asset_owner',
        ]

        # Set the form field data for email fields to the actual user email address - by default it's the User ID.
        for field in self._email_fields:
            if getattr(self.instance, field):
                self.initial[field] = getattr(self.instance, field).email


class VisualisationApprovalForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = VisualisationApproval
        fields = ['approved', 'visualisation', 'approver']
        widgets = {"visualisation": HiddenInput, "approver": HiddenInput}
        labels = {"approved": "I have reviewed this visualisation"}

    def __init__(self, *args, **kwargs):
        # If the visualisation has already been approved, we want to render a form that allows the user to unapprove it.
        if kwargs.get('instance') and kwargs.get('instance').approved:
            self._initial_approved = True
            self.Meta.widgets["approved"] = HiddenInput
            kwargs['initial']['approved'] = False
        else:
            self._initial_approved = False

        super().__init__(*args, **kwargs)

        if self._initial_approved:
            self.fields['approved'].required = False

    def clean_approved(self):
        if not self._initial_approved and not self.cleaned_data['approved']:
            raise ValidationError(
                "You must confirm that you have reviewed this visualisation"
            )
        return self.cleaned_data['approved']
