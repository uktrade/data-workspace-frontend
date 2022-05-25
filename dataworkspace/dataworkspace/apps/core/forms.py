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
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemWidgetMixin,
)


class ConditionalSupportTypeRadioWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.RadioSelect):
    template_name = "design_system/radio.html"
    option_template_name = "core/partial/support_type_radio_option.html"


class SupportForm(GOVUKDesignSystemForm):
    class SupportTypes(models.TextChoices):
        TECH_SUPPORT = "tech", "I would like to have technical support"
        NEW_DATASET = "dataset", "I would like to add a new dataset"
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
        error_messages={"required": "Please select the type of support you require."},
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
    how_satisfied = GOVUKDesignSystemRadioField(
        required=True,
        label="1. Overall how satisfied are you with the current Data Workspace?",
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", label_size="m", small=True),
        choices=[(t.value, t.label) for t in HowSatisfiedType],
    )

    trying_to_do = GOVUKDesignSystemMultipleChoiceField(
        required=False,
        label="2. What were you trying to do today? (optional)",
        help_text="Select all options that are relevant to you.",
        widget=GOVUKDesignSystemCheckboxesWidget(heading="h2", label_size="m", small=True),
        choices=[(t.value, t.label) for t in TryingToDoType],
    )

    improve_service = GOVUKDesignSystemTextareaField(
        required=False,
        label="3. How could we improve the service? (optional)",
        help_html=render_to_string("core/partial/user-survey-improve-service-hint.html"),
        widget=GOVUKDesignSystemTextareaWidget(heading="h2", label_size="m"),
    )


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
