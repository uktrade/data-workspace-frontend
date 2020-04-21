from django.forms import ModelForm, Textarea, TextInput, Select, CheckboxInput


class GOVUKDesignSystemModelForm(ModelForm):
    """A base form that applies basic GOV.UK Design System form field styles.

    This will probably only work for the most basic forms. If we end up needing more complex forms this will need
    further work/thought (as well as the corresponding partial template that must be manually used to render the
    fields (`partials/govuk_basic_form_field.html`).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, TextInput):
                field.widget.attrs.update({"class": "govuk-input"})
            elif isinstance(field.widget, Textarea):
                field.widget.attrs.update({"class": "govuk-textarea"})
            elif isinstance(field.widget, Select):
                field.widget.attrs.update({"class": "govuk-select"})
            elif isinstance(field.widget, CheckboxInput):
                field.widget.attrs.update({"class": "govuk-checkboxes__input"})
