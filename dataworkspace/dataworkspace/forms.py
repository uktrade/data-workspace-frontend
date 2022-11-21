import copy

import re

from django import forms
from django.contrib.admin.widgets import AdminTextareaWidget
from django.core.validators import EmailValidator
from django.forms import (
    CheckboxInput,
    CharField,
    EmailField,
    Media,
    ModelChoiceField,
)
from django.utils.html import linebreaks


class GOVUKDesignSystemWidgetMixin:
    def __init__(
        self,
        *,
        label_is_heading=True,
        heading="h1",
        heading_class="govuk-label-wrapper",
        label_size="l",
        extra_label_classes="",
        small=False,
        show_selected_file=False,
        data_attributes: dict = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.custom_context = dict(
            label_is_heading=label_is_heading,
            heading=heading,
            heading_class=heading_class,
            label_size=label_size,
            extra_label_classes=extra_label_classes,
            small=small,
            show_selected_file=show_selected_file,
            data_attributes=data_attributes,
        )

    def __deepcopy__(self, memo):
        obj = copy.copy(self)
        obj.custom_context = self.custom_context.copy()
        memo[id(self)] = obj
        return obj

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(self.custom_context)

        return context


class GOVUKDesignSystemFieldMixin:
    """
    Must be mixed-in with another class of type django.forms.Field.
    """

    widget: GOVUKDesignSystemWidgetMixin
    label: str
    help_text: str

    def __init__(self, *, help_text=None, help_html=None, **kwargs):
        if help_text is not None and help_html is not None:
            raise ValueError("Only one of `help_text` and `help_html` is supported")

        self.help_html = help_html

        super().__init__(help_text=help_text, **kwargs)

        self.widget.custom_context["label"] = self.label
        self.widget.custom_context["help_text"] = self.help_text
        self.widget.custom_context["help_html"] = self.help_html


class GOVUKDesignSystemTextWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.TextInput):
    template_name = "design_system/textinput.html"


class GOVUKDesignSystemEmailWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.EmailInput):
    template_name = "design_system/textinput.html"


class GOVUKDesignSystemTextareaWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.Textarea):
    template_name = "design_system/textarea.html"


class GOVUKDesignSystemRichTextWidget(GOVUKDesignSystemTextareaWidget):
    class Media:
        js = (
            "assets/vendor/ckeditor5/ckeditor.js",
            "js/text-editor.js",
        )


class GOVUKDesignSystemPlainTextareaWidget(GOVUKDesignSystemTextareaWidget):
    def format_value(self, value):
        value = super().format_value(value)

        if not value:
            return value

        # Strip out any html tags and allow the user to edit just the text
        # Which means that any hyperlink targets will be lost!
        # It isn't perfect, but it's a workaround until we include a
        # rich text editor in the DW frontend
        return re.sub("<[^<]+?>", "", value)


class GOVUKDesignSystemRadiosWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.RadioSelect):
    template_name = "design_system/radio.html"
    option_template_name = "design_system/radio_option.html"


class GOVUKDesignSystemCheckboxesWidget(
    GOVUKDesignSystemWidgetMixin, forms.widgets.CheckboxSelectMultiple
):
    template_name = "design_system/checkbox.html"
    option_template_name = "design_system/checkbox_option.html"


class GOVUKDesignSystemFileInputWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.FileInput):
    template_name = "design_system/file.html"

    def format_value(self, value):
        """
        Return the file object if it has a defined url attribute.
        """
        if value:
            return value.name.split("!")[0]
        return super().format_value(value)


class GOVUKDesignSystemMultipleChoiceField(GOVUKDesignSystemFieldMixin, forms.MultipleChoiceField):
    widget = GOVUKDesignSystemCheckboxesWidget


class GOVUKDesignSystemCharField(GOVUKDesignSystemFieldMixin, CharField):
    widget = GOVUKDesignSystemTextWidget


class GOVUKDesignSystemEmailField(GOVUKDesignSystemFieldMixin, EmailField):
    widget = GOVUKDesignSystemTextWidget


class GOVUKDesignSystemTextareaField(GOVUKDesignSystemCharField):
    widget = GOVUKDesignSystemTextareaWidget


class GOVUKDesignSystemPlainTextareaField(GOVUKDesignSystemTextareaField):
    widget = GOVUKDesignSystemPlainTextareaWidget

    def clean(self, value):
        # We want to convert new lines to html <br> tags as the inverse to
        # what happens in GOVUKDesignSystemPlainTextareaWidget.format_value
        # which is a workaround until we add a rich html editor to the front end
        value = linebreaks(value)
        return super().clean(value)


class GOVUKDesignSystemRadioField(GOVUKDesignSystemFieldMixin, forms.ChoiceField):
    widget = GOVUKDesignSystemRadiosWidget


class GOVUKDesignSystemSingleCheckboxWidget(GOVUKDesignSystemWidgetMixin, CheckboxInput):
    template_name = "design_system/single_checkbox.html"


class GOVUKDesignSystemBooleanField(GOVUKDesignSystemFieldMixin, forms.BooleanField):
    widget = GOVUKDesignSystemSingleCheckboxWidget


class GOVUKDesignSystemSelectWidget(GOVUKDesignSystemWidgetMixin, forms.widgets.Select):
    template_name = "design_system/select.html"


class GOVUKDesignSystemChoiceField(GOVUKDesignSystemFieldMixin, forms.ChoiceField):
    widget = GOVUKDesignSystemSelectWidget


class GOVUKDesignSystemEmailValidationModelChoiceField(
    GOVUKDesignSystemFieldMixin, ModelChoiceField
):
    widget = GOVUKDesignSystemTextWidget

    def clean(self, value):
        if value:
            EmailValidator(message=self.error_messages["invalid_email"])(value.lower())
        return super().clean(value.lower() if value else value)


class GOVUKDesignSystemFileField(GOVUKDesignSystemFieldMixin, forms.FileField):
    widget = GOVUKDesignSystemFileInputWidget


class GOVUKDesignSystemRichTextField(GOVUKDesignSystemFieldMixin, forms.CharField):
    widget = GOVUKDesignSystemRichTextWidget(data_attributes={"type": "rich-text-editor"})


class GOVUKDesignSystemModelForm(forms.ModelForm):
    def clean(self):
        """We need to attach errors to widgets so that the fields can be rendered correctly. This slightly breaks
        the Django model, which doesn't expose errors/validation to widgets as standard. We need to do this
        in order to render GOV.UK Design System validation correctly."""
        cleaned_data = super().clean()

        if self.is_bound:
            for field in self:
                if self.errors.get(field.name) and not isinstance(
                    self.fields[field.name].widget, forms.HiddenInput
                ):
                    self.fields[field.name].widget.custom_context["errors"] = self.errors[
                        field.name
                    ]

        return cleaned_data

    @property
    def summary_errors(self):
        """
        Prepare a data structure containing all of the errors in order to render an `error summary` GOV.UK Design
        System component.
        """
        field_errors = [(field.id_for_label, field.errors[0]) for field in self if field.errors]
        non_field_errors = [(None, e) for e in self.non_field_errors()]

        return non_field_errors + field_errors


class GOVUKDesignSystemForm(forms.Form):
    """This is duplicated from above because of issues using a mixin. Feels like it should be possible..."""

    def clean(self):
        """We need to attach errors to widgets so that the fields can be rendered correctly. This slightly breaks
        the Django model, which doesn't expose errors/validation to widgets as standard. We need to do this
        in order to render GOV.UK Design System validation correctly."""
        cleaned_data = super().clean()

        if self.is_bound:
            for field in self:
                if self.errors.get(field.name) and not isinstance(
                    self.fields[field.name].widget, forms.HiddenInput
                ):
                    self.fields[field.name].widget.custom_context["errors"] = self.errors[
                        field.name
                    ]

        return cleaned_data

    @property
    def summary_errors(self):
        """
        Prepare a data structure containing all of the errors in order to render an `error summary` GOV.UK Design
        System component.
        """
        field_errors = [(field.id_for_label, field.errors[0]) for field in self if field.errors]
        non_field_errors = [(None, e) for e in self.non_field_errors()]

        return non_field_errors + field_errors


class AdminRichTextEditorWidget(AdminTextareaWidget):
    def __init__(self, attrs=None):
        super().__init__(attrs={"data-type": "rich-text-editor", **(attrs or {})})

    @property
    def media(self):
        return Media(
            js=(
                "assets/vendor/ckeditor5/ckeditor.js",
                "js/text-editor.js",
            ),
            css={"all": ["admin/css/rich-text.css"]},
        )
