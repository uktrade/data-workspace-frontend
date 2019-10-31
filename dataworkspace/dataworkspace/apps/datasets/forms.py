from django import forms


class RequestAccessForm(forms.Form):
    email = forms.CharField(widget=forms.TextInput, required=True)
    goal = forms.CharField(widget=forms.Textarea, required=True)
    justification = forms.CharField(widget=forms.Textarea, required=True)
    team = forms.CharField(widget=forms.TextInput, required=True)
