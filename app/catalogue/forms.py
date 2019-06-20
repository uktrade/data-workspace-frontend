from django import forms


class ContactForm(forms.Form):
    email = forms.EmailField()
    summary = forms.TextInput()
    description = forms.Textarea()

    issue_type = forms.RadioSelect()