from django import forms
from django.utils.safestring import mark_safe


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
<p class="govuk-hint">Please use this form to give us feedback, report a technical issue or request data that is not available on Data Workspace.</p>
<p class="govuk-hint">If you had a technical issue, briefly explain:</p>
<ul class="govuk-list govuk-list--bullet govuk-hint">
  <li>what you did</li>
  <li>what happened</li>
  <li>what you expected to happen</li>
</ul>"""
            )
        ),
    )
