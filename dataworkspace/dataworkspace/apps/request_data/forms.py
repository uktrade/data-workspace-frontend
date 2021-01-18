from django import forms
from django.template.loader import render_to_string

from dataworkspace.apps.request_data.models import (
    DataRequest,
    RoleType,
    SecurityClassificationType,
)
from dataworkspace.forms import (
    NewGOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemTextWidget,
)


class RequestDataWhoAreYouForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['requester_role']

    requester_role = forms.ChoiceField(
        choices=[(t.value, t.label) for t in RoleType],
        widget=GOVUKDesignSystemRadiosWidget(
            "Who are you in relation to this request?"
        ),
        error_messages={
            "required": "You must declare your role in this request for data."
        },
    )


class RequestDataDescriptionForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_description']

    data_description = forms.CharField(
        widget=GOVUKDesignSystemTextareaWidget(
            "Describe the data you want to add",
            hint_html=render_to_string('request_data/data-description-hint.html'),
        ),
        error_messages={"required": "Enter a description of the data."},
    )


class RequestDataPurposeForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_purpose']

    data_purpose = forms.CharField(
        widget=GOVUKDesignSystemTextareaWidget(
            "What will the data be used for?",
            hint_text=(
                "Please provide reasons why the data will help deliver your or another team’s priorities. "
                "Include details of any outputs you will create with the data and the intended audience. "
                "For example, “I will use the data to build a KPI dashboard for the monthly People, "
                "Finance and Risk Committee”."
            ),
        ),
        error_messages={"required": "Enter the intended use of the data."},
    )


class RequestDataSecurityClassificationForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['security_classification']

    security_classification = forms.ChoiceField(
        choices=[(t.value, t.label) for t in SecurityClassificationType],
        widget=GOVUKDesignSystemRadiosWidget(
            "What is the security classification of this data?",
            hint_html=render_to_string(
                'request_data/security-classification-hint.html'
            ),
        ),
        error_messages={
            "required": "You must declare the security classification of the data."
        },
    )


class RequestDataLocationForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_location']

    data_location = forms.CharField(
        widget=GOVUKDesignSystemTextareaWidget(
            "Where is the data currently held?",
            hint_html=render_to_string('request_data/data-location-hint.html'),
        ),
        required=False,
    )


class RequestDataOwnerOrManagerForm(NewGOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['name_of_owner_or_manager']

    name_of_owner_or_manager = forms.CharField(
        widget=GOVUKDesignSystemTextWidget(
            "Name of information asset owner or manager",
            hint_text=(
                "An Information Asset Owner or Manager is the person who is responsible for ensuring information "
                "assets are handled and managed appropriately. If you don’t know their name, please leave blank."
            ),
        ),
        required=False,
    )
