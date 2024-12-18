from django import forms
from django.db import models
from django.template.loader import render_to_string

from dataworkspace.apps.core.models import HowSatisfiedType, TryingToDoType
from dataworkspace.forms import (
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemCheckboxesWidget,
    GOVUKDesignSystemEmailField,
    GOVUKDesignSystemEmailWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemMultipleChoiceField,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemWidgetMixin,
)


class ConditionalSupportTypeRadioWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.RadioSelect):
    template_name = "design_system/radio.html"
    option_template_name = "core/partial/support_type_radio_option.html"


class ConditionalSupportTypeCheckboxWidget(
    GOVUKDesignSystemCheckboxesWidget, forms.widgets.CheckboxSelectMultiple
):
    template_name = "design_system/checkbox.html"
    option_template_name = "core/partial/support_type_checkbox_option.html"


class AddDatasetRequestForm(GOVUKDesignSystemForm):
    email = forms.EmailField(widget=forms.HiddenInput())
    message = GOVUKDesignSystemTextareaField(
        help_html=render_to_string("core/partial/add-dataset-request-hint.html"),
        label="Tell us about the data you want to add",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
            extra_label_classes="govuk-!-static-margin-0",
        ),
        error_messages={"required": "Enter information about the data you want to add"},
    )


class CustomVisualisationReviewForm(GOVUKDesignSystemForm):
    email = forms.EmailField(widget=forms.HiddenInput())
    message = GOVUKDesignSystemTextareaField(
        help_html=render_to_string("core/partial/custom-visualisation-review-hint.html"),
        label="Tell us about your visualisation",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            extra_label_classes="govuk-!-static-margin-0",
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter your visualisation's name"},
    )


class SupportAnalysisDatasetForm(GOVUKDesignSystemForm):
    email = forms.EmailField(widget=forms.HiddenInput())
    message = GOVUKDesignSystemTextareaField(
        label="Tell us what you need support with",
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            label_is_heading=True,
            attrs={"rows": 5},
        ),
        error_messages={"required": "Enter details about the support or advice you need"},
    )


class SupportForm(GOVUKDesignSystemForm):
    class SupportTypes(models.TextChoices):
        TECH_SUPPORT = "tech", "I need technical support"
        NEW_DATASET = "dataset", "I want to add a new dataset"
        DATA_ANALYSIS_SUPPORT = "analysis", "I need data analysis support or advice"
        VISUALISATION_REVIEW = "visualisation", "I need a custom visualisation reviewed"
        OTHER = "other", "Other"

    email = GOVUKDesignSystemEmailField(
        label="Your email address",
        required=False,
        widget=GOVUKDesignSystemEmailWidget(label_is_heading=False),
    )
    support_type = GOVUKDesignSystemRadioField(
        label="How can we help you?",
        help_text="Please choose one of the options below for help.",
        choices=SupportTypes.choices,
        widget=ConditionalSupportTypeRadioWidget(heading="h2"),
        error_messages={"required": "Please select the type of support you require"},
    )
    message = GOVUKDesignSystemTextareaField(
        required=False,
        label="Tell us how we can help you",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 5},
        ),
    )

    def clean(self):
        cleaned = super().clean()

        if cleaned["support_type"] in [
            self.SupportTypes.TECH_SUPPORT,
            self.SupportTypes.OTHER,
        ] and not cleaned.get("email"):
            raise forms.ValidationError({"email": "Please enter your email address"})

        if cleaned["support_type"] == self.SupportTypes.OTHER and not cleaned["message"]:
            raise forms.ValidationError({"message": "Please enter your support message"})


class UserSatisfactionSurveyForm(GOVUKDesignSystemForm):
    def __init__(self, *args, **kwargs):
        trying_to_do_initial = kwargs.pop("trying_to_do_initial", None)
        super().__init__(*args, **kwargs)

        self.fields["survey_source"].initial = "contact-us"

        if "csat-link" in trying_to_do_initial:
            self.fields["trying_to_do"].initial = "analyse-data"
            self.fields["survey_source"].initial = "csat-download-link"

    survey_source = forms.CharField(widget=forms.HiddenInput())

    trying_to_do = GOVUKDesignSystemMultipleChoiceField(
        required=True,
        label="What were you trying to do today?",
        help_text="Select all options that are relevant to you.",
        widget=ConditionalSupportTypeCheckboxWidget(heading="h2", label_size="m"),
        choices=[(t.value, t.label) for t in TryingToDoType],
        error_messages={
            "required": "Select at least one option for what were you trying to do today"
        },
    )

    trying_to_do_other_message = GOVUKDesignSystemCharField(
        required=False,
        label="Tell us what you were doing",
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False, label_size="m"),
    )

    how_satisfied = GOVUKDesignSystemRadioField(
        required=True,
        label="How do you feel about your experience of using Data Workspace today?",
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", label_size="m"),
        choices=[(t.value, t.label) for t in HowSatisfiedType],
        error_messages={"required": "Select how Data Workspace made you feel today"},
    )

    improve_service = GOVUKDesignSystemTextareaField(
        required=False,
        label="How could we improve the service? (optional)",
        help_html=render_to_string("core/partial/user-survey-improve-service-hint.html"),
        widget=GOVUKDesignSystemTextareaWidget(
            heading="h2",
            label_size="m",
            # extra_label_classes="govuk-!-static-margin-0",
        ),
    )

    def clean_trying_to_do_other_message(self):
        trying_to_do = self.cleaned_data.get("trying_to_do")
        trying_to_do_other_message = self.cleaned_data.get("trying_to_do_other_message")
        if not trying_to_do_other_message and trying_to_do and "other" in trying_to_do:
            raise forms.ValidationError("Enter a description for what you were doing")
        return trying_to_do_other_message


class NewsletterSubscriptionForm(forms.Form):
    submit_action = forms.CharField()
    email = forms.CharField(required=True)


class TechnicalSupportForm(GOVUKDesignSystemForm):
    email = forms.EmailField(widget=forms.HiddenInput())
    what_were_you_doing = GOVUKDesignSystemCharField(
        required=False,
        label="What were you trying to do?",
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False),
    )
    what_happened = GOVUKDesignSystemTextareaField(
        required=False,
        label="What happened?",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 5},
        ),
    )
    what_should_have_happened = GOVUKDesignSystemTextareaField(
        required=False,
        label="What should have happened?",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            attrs={"rows": 5},
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if (
            not cleaned["what_were_you_doing"]
            and not cleaned["what_happened"]
            and not cleaned["what_should_have_happened"]
        ):
            raise forms.ValidationError("Please add some detail to the support request")


class ContactUsForm(GOVUKDesignSystemForm):
    class ContactTypes(models.TextChoices):
        GET_HELP = "help", "Get help"
        GIVE_FEEDBACK = "feedback", "Give feedback"

    contact_type = GOVUKDesignSystemRadioField(
        required=False,
        label="What would you like to do?",
        choices=ContactTypes.choices,
        widget=ConditionalSupportTypeRadioWidget(heading="h2"),
    )

    def clean_contact_type(self):
        contact_type = self.cleaned_data.get("contact_type")
        if not contact_type:
            raise forms.ValidationError("Select what you would like to do")
        return contact_type
