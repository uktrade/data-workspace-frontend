from django import forms


class DatasetFindForm(forms.Form):
    q = forms.CharField(required=False)
