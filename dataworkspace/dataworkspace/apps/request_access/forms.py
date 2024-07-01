from datetime import datetime, timedelta, date
import calendar
from django import forms
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError

from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.forms import (
    GOVUKDesignSystemBooleanField,
    GOVUKDesignSystemDateField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemSingleCheckboxWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
    GOVUKDesignSystemDateWidget,
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


class ToolsAccessRequestFormPart1(GOVUKDesignSystemModelForm):
    class Meta:
        model = AccessRequest
        fields = ["training_screenshot"]

    training_screenshot = GOVUKDesignSystemFileField(
        label="Security and Data Protection training evidence",
        help_html=render_to_string("request_access/training-screenshot-hint.html"),
        widget=GOVUKDesignSystemFileInputWidget(
            label_is_heading=True,
            heading="h2",
            heading_class="govuk-heading-m",
            extra_label_classes="govuk-!-font-weight-bold",
            show_selected_file=True,
        ),
        error_messages={"required": "You must upload proof that you've completed the training."},
    )


class ToolsAccessRequestFormPart2(GOVUKDesignSystemModelForm):
    class Meta:
        model = AccessRequest
        fields = ["spss_and_stata"]

    spss_and_stata = GOVUKDesignSystemBooleanField(
        label="Stata",
        help_html=render_to_string("request_access/spss-and-stata-hint.html"),
        required=False,
        widget=GOVUKDesignSystemRadiosWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            choices=((True, "Yes"), (False, "No")),
        ),
    )


class ToolsAccessRequestFormPart3(GOVUKDesignSystemModelForm):
    class Meta:
        model = AccessRequest
        fields = ["line_manager_email_address", "reason_for_spss_and_stata"]

    line_manager_email_address = GOVUKDesignSystemCharField(
        label="What is your line manager's email address?",
        help_text="We will use this to email your line manager to ask for approval.",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide your line manager's email address."},
    )

    reason_for_spss_and_stata = GOVUKDesignSystemTextareaField(
        label="What is your reason for needing Stata?",
        help_text="We're asking these questions to give you access to Stata tools.",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter a reason for needing STATA."},
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
