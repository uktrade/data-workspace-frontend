from django import forms
from django.forms import ModelForm, Textarea, TextInput, Select, CheckboxInput


class GOVUKDesignSystemTextWidget(forms.widgets.TextInput):
    template_name = 'design_system/textinput.html'
    errors = None
    label_sizes = {
        "h1": "l",
        "h2": "m",
        "h3": "s",
    }

    def __init__(
        self,
        label,
        attrs=None,
        hint_text=None,
        hint_html=None,
        heading='h1',
        *args,
        **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        if hint_text and hint_html:
            raise ValueError("Only one of `hint_text` and `hint_html` is supported")

        super().__init__(attrs)

        self._label = label
        self._hint_text = hint_text
        self._hint_html = hint_html
        self._heading = heading

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['label'] = self._label
        context['widget']['heading'] = self._heading
        context['widget']['hint_text'] = self._hint_text
        context['widget']['hint_html'] = self._hint_html
        context['widget']['label'] = self._label
        context['widget']['errors'] = self.errors
        context['widget']['label_size'] = self.label_sizes.get(
            self._heading, self.label_sizes['h1']
        )

        return context


class GOVUKDesignSystemTextareaWidget(forms.widgets.Textarea):
    template_name = 'design_system/textarea.html'
    errors = None
    label_sizes = {
        "h1": "l",
        "h2": "m",
        "h3": "s",
    }

    def __init__(
        self,
        label,
        attrs=None,
        hint_text=None,
        hint_html=None,
        heading='h1',
        *args,
        **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        if hint_text and hint_html:
            raise ValueError("Only one of `hint_text` and `hint_html` is supported")

        super().__init__(attrs)

        self._label = label
        self._hint_text = hint_text
        self._hint_html = hint_html
        self._heading = heading

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['label'] = self._label
        context['widget']['heading'] = self._heading
        context['widget']['hint_text'] = self._hint_text
        context['widget']['hint_html'] = self._hint_html
        context['widget']['label'] = self._label
        context['widget']['errors'] = self.errors
        context['widget']['label_size'] = self.label_sizes.get(
            self._heading, self.label_sizes['h1']
        )

        return context


class GOVUKDesignSystemRadiosWidget(forms.widgets.RadioSelect):
    template_name = 'design_system/radio.html'
    option_template_name = "design_system/radio_option.html"
    errors = None
    legend_sizes = {
        "h1": "l",
        "h2": "m",
        "h3": "s",
    }

    def __init__(
        self,
        label,
        attrs=None,
        hint_text=None,
        hint_html=None,
        heading='h1',
        *args,
        **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        if hint_text and hint_html:
            raise ValueError("Only one of `hint_text` and `hint_html` is supported")

        super().__init__(attrs)
        self._label = label
        self._hint_text = hint_text
        self._hint_html = hint_html
        self._heading = heading

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['label'] = self._label
        context['widget']['hint_text'] = self._hint_text
        context['widget']['hint_html'] = self._hint_html
        context['widget']['heading'] = self._heading
        context['widget']['errors'] = self.errors
        context['widget']['legend_size'] = self.legend_sizes.get(
            self._heading, self.legend_sizes['h1']
        )

        return context


class NewGOVUKDesignSystemModelForm(forms.ModelForm):
    def clean(self):
        """We need to attach errors to widgets so that the fields can be rendered correctly. This slightly breaks
        the Django model, which doesn't expose errors/validation to widgets as standard. We need to do this
        in order to render GOV.UK Design System validation correctly."""
        cleaned_data = super().clean()

        if self.is_bound:
            for field in self:
                if self.errors.get(field.name):
                    self.fields[field.name].widget.errors = self.errors[field.name]
                print(field)

        return cleaned_data

    @property
    def summary_errors(self):
        """
        Prepare a data structure containing all of the errors in order to render an `error summary` GOV.UK Design
        System component.
        """
        field_errors = [
            (field.id_for_label, field.errors[0]) for field in self if field.errors
        ]
        non_field_errors = [(None, e) for e in self.non_field_errors()]

        return non_field_errors + field_errors


class GOVUKDesignSystemModelForm(ModelForm):
    """A base form that applies basic GOV.UK Design System form field styles.

    This will probably only work for the most basic forms. If we end up needing more complex forms this will need
    further work/thought (as well as the corresponding partial template that must be manually used to render the
    fields (`partials/govuk_basic_form_field.html`).

    DEPRECATED: Use and extend the `NewGOVUKDesignSystemModelForm` class above.
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
