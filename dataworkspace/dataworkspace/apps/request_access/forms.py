from django import forms
from django.template.loader import render_to_string

from dataworkspace.apps.request_access.models import AccessRequest
from dataworkspace.forms import (
    GOVUKDesignSystemBooleanField,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemFileField,
    GOVUKDesignSystemFileInputWidget,
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
        label="Security and Data Protection training screenshot",
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
        label="SPSS and Stata",
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
        label="What is your reason for needing SPSS and Stata?",
        help_text="We're asking these questions to give you access to SPSS and Stata tools.",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter a reason for needing SPSS and STATA."},
    )
