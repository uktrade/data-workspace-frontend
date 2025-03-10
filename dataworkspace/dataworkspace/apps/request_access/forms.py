import calendar
from datetime import date, datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.forms import (
    GOVUKDesignSystemBooleanField,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemDateField,
    GOVUKDesignSystemDateWidget,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemSingleCheckboxWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemTextWidget,
)


class DatasetAccessRequestForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = AccessRequest
        fields = ["id", "contact_email", "reason_for_access"]

    id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    contact_email = GOVUKDesignSystemCharField(
        label="Contact email",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide your contact email address."},
    )

    reason_for_access = GOVUKDesignSystemTextareaField(
        label="Why do you need this data?",
        help_html=render_to_string("request_access/reason-for-access-hint.html"),
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter a reason for requesting this data."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        initial_email = self.initial.get("contact_email")
        if initial_email:
            self.fields["contact_email"].help_text = f"You are logged in as {initial_email}"
            self.fields["contact_email"].widget.custom_context[
                "help_text"
            ] = f"You are logged in as {initial_email}"


class ToolsAccessRequestForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = AccessRequest
        fields = ["training_screenshot"]

    training_screenshot = GOVUKDesignSystemFileField(
        label="Upload file",
        widget=GOVUKDesignSystemFileInputWidget(
            label_is_heading=False,
            label_size="small",
            heading="h2",
            heading_class="govuk-heading-m",
            show_selected_file=True,
        ),
        error_messages={"required": "You must upload proof that you've completed the training."},
    )


class SelfCertifyForm(GOVUKDesignSystemForm):
    invalid_date_message = (
        "The date on your Security and Data Protection certificate must be a real date"
    )

    def clean_certificate_date(self):
        cleaned_data = super().clean()
        given_date = cleaned_data["certificate_date"]
        total_days = 366 if calendar.isleap(date.today().year) else 365
        one_year_ago = datetime.now() - timedelta(days=total_days)
        if one_year_ago >= given_date or given_date > datetime.now():
            raise ValidationError(
                "Enter the date that’s on your security and data protection certificate, this date must be today or within the past 12 months",  # pylint: disable=line-too-long
                code="not_in_range_date",
            )
        return given_date

    certificate_date = GOVUKDesignSystemDateField(
        label="Enter the date that's on your certificate",
        help_text="For example, 27 3 2007",
        error_messages={
            "required": "Enter the date that's on your Security and Data Protection certificate",
            "invalid_date": invalid_date_message,
            "invalid_day": invalid_date_message,
            "invalid_month": invalid_date_message,
            "invalid_year": invalid_date_message,
        },
        widget=GOVUKDesignSystemDateWidget(
            day_attrs={
                "label": "Day",
                "label_is_heading": False,
                "inputmode": "numeric",
                "extra_input_classes": "govuk-date-input__input govuk-input--width-2",
            },
            month_attrs={
                "label": "Month",
                "label_is_heading": False,
                "inputmode": "numeric",
                "extra_input_classes": "govuk-date-input__input govuk-input--width-2",
            },
            year_attrs={
                "label": "Year",
                "label_is_heading": False,
                "inputmode": "numeric",
                "extra_input_classes": "govuk-date-input__input govuk-input--width-4",
            },
        ),
    )

    declaration = GOVUKDesignSystemBooleanField(
        label="I confirm that I've completed the Security and Data Protection training and the date I've entered matches my certificate.",  # pylint: disable=line-too-long
        error_messages={
            "required": "Check the box to agree with the declaration statement",
        },
        widget=GOVUKDesignSystemSingleCheckboxWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
    )


class StataAccessForm(GOVUKDesignSystemForm):
    class Meta:
        model = AccessRequest
        fields = ["reason_for_spss_and_stata"]

    reason_for_spss_and_stata = GOVUKDesignSystemTextareaField(
        help_text="Use this space to specify why you need to use STATA instead of other tools.",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Explain why you need to use STATA"},
    )
