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


class ConditionalSupportTypeCheckboxWidget(
    GOVUKDesignSystemCheckboxesWidget, forms.widgets.CheckboxSelectMultiple
):
    template_name = "design_system/checkbox.html"
    option_template_name = "core/partial/support_type_checkbox_option.html"


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
    trying_to_do = GOVUKDesignSystemMultipleChoiceField(
        required=True,
        label="1. What were you trying to do today?",
        help_text="Select all options that are relevant to you.",
        widget=ConditionalSupportTypeCheckboxWidget(heading="h2", label_size="m", small=True),
        choices=[(t.value, t.label) for t in TryingToDoType],
        error_messages={
            "required": "Select one or more options that explain what you were trying to do today."
        },
    )

    trying_to_do_other_message = GOVUKDesignSystemCharField(
        required=False,
        label="Tell us what you were doing",
        widget=GOVUKDesignSystemTextWidget(label_is_heading=False, label_size="m"),
    )

    how_satisfied = GOVUKDesignSystemRadioField(
        required=True,
        label="2. How do you feel about your experience of using Data Workspace today?",
        widget=GOVUKDesignSystemRadiosWidget(heading="h2", label_size="m", small=True),
        choices=[(t.value, t.label) for t in HowSatisfiedType],
        error_messages={
            "required": "Select an option for how Data workspace made you feel today."
        },
    )

    describe_experience = GOVUKDesignSystemTextareaField(
        required=False,
        label="3. Describe your experience (optional)",
        widget=GOVUKDesignSystemTextareaWidget(heading="h2", label_size="m"),
    )

    improve_service = GOVUKDesignSystemTextareaField(
        required=False,
        label="4. How could we improve the service? (optional)",
        help_html=render_to_string("core/partial/user-survey-improve-service-hint.html"),
        widget=GOVUKDesignSystemTextareaWidget(heading="h2", label_size="m"),
    )

    def clean_trying_to_do_other_message(self):
        trying_to_do = self.cleaned_data.get("trying_to_do")
        trying_to_do_other_message = self.cleaned_data.get("trying_to_do_other_message")
        if not trying_to_do_other_message and trying_to_do and "other" in trying_to_do:
            raise forms.ValidationError("'Tell us what you were doing' cannot be blank")
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
            raise forms.ValidationError("Select an option for what you would like to do")
        return contact_type
