from django import forms
from django.utils.safestring import mark_safe

from dataworkspace.apps.core.models import HowSatisfiedType, TryingToDoType
from dataworkspace.forms import (
    GOVUKDesignSystemCheckboxesWidget,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemMultipleChoiceField,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
)


class SupportForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label='Your email address',
        widget=forms.EmailInput(attrs={'class': 'govuk-input'}),
    )
    message = forms.CharField(
        required=True,
        label='Description',
        widget=forms.Textarea(attrs={'class': 'govuk-textarea'}),
        #
        # If you're here because you want to copy the help text (i.e. bullets as form hints), then please don't. If
        # this needs to be reused, we should probably do something else (e.g. convert it to markdown and add a markdown
        # filter that can output GOV.UK Design System-aware elements). So this HTML-in-code should either remain an
        # exception or eventually disappear.
        help_text=(
            mark_safe(
                """
<p class="govuk-hint">Please use this form to give us feedback or report a technical issue on Data Workspace.</p>
<p class="govuk-hint">If you had a technical issue, briefly explain:</p>
<ul class="govuk-list govuk-list--bullet govuk-hint">
  <li>what you did</li>
  <li>what happened</li>
  <li>what you expected to happen</li>
</ul>"""
            )
        ),
    )


class UserSatisfactionSurveyForm(GOVUKDesignSystemForm):
    how_satisfied = GOVUKDesignSystemRadioField(
        required=True,
        label='1. Overall how satisfied are you with the current Data Workspace?',
        widget=GOVUKDesignSystemRadiosWidget(heading='h2', label_size='m', small=True),
        choices=[(t.value, t.label) for t in HowSatisfiedType],
    )

    trying_to_do = GOVUKDesignSystemMultipleChoiceField(
        required=False,
        label='2. What were you trying to do today? (optional)',
        help_text='Select all options that are relevant to you.',
        widget=GOVUKDesignSystemCheckboxesWidget(
            heading='h2', label_size='m', small=True
        ),
        choices=[(t.value, t.label) for t in TryingToDoType],
    )

    improve_service = GOVUKDesignSystemTextareaField(
        required=False,
        label='3. How could we improve the service? (optional)',
        help_text="""Do not include any personal information,
                 like your name or email address. We'll delete any personal information you
                 do include""",
        widget=GOVUKDesignSystemTextareaWidget(heading='h2', label_size='m'),
    )
