from django.template.loader import render_to_string

from dataworkspace.apps.request_data.models import (
    DataRequest,
    RoleType,
    SecurityClassificationType,
)
from dataworkspace.forms import (
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemRadioField,
)


class RequestDataWhoAreYouForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['requester_role']

    requester_role = GOVUKDesignSystemRadioField(
        label="Are you the information asset owner or manager for the data?",
        choices=[(t.value, t.label) for t in RoleType],
        widget=GOVUKDesignSystemRadiosWidget,
        error_messages={"required": "You must declare your role in this request for data."},
    )


class RequestDataDescriptionForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_description']

    data_description = GOVUKDesignSystemTextareaField(
        label="Describe the data you want to add",
        help_html=render_to_string('request_data/data-description-hint.html'),
        error_messages={"required": "Enter a description of the data."},
    )


class RequestDataPurposeForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_purpose']

    data_purpose = GOVUKDesignSystemTextareaField(
        label="What will the data be used for?",
        help_text=(
            "Please provide reasons why the data will help deliver your or another team’s priorities. "
            "Include details of any outputs you will create with the data and the intended audience. "
            "For example, “I will use the data to build a KPI dashboard for the monthly People, "
            "Finance and Risk Committee”."
        ),
        error_messages={"required": "Enter the intended use of the data."},
    )


class RequestDataSecurityClassificationForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['security_classification']

    security_classification = GOVUKDesignSystemRadioField(
        label="What is the security classification of this data?",
        help_html=render_to_string('request_data/security-classification-hint.html'),
        choices=[(t.value, t.label) for t in SecurityClassificationType],
        widget=GOVUKDesignSystemRadiosWidget,
        error_messages={"required": "You must declare the security classification of the data."},
    )


class RequestDataLocationForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_location']

    data_location = GOVUKDesignSystemTextareaField(
        label="Where is the data currently held?",
        help_html=render_to_string('request_data/data-location-hint.html'),
        required=False,
    )


class RequestDataOwnerOrManagerForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['name_of_owner_or_manager']

    name_of_owner_or_manager = GOVUKDesignSystemCharField(
        label="Name of information asset owner or manager",
        help_text=(
            "An Information Asset Owner or Manager is the person who is responsible for ensuring information "
            "assets are handled and managed appropriately. If you don’t know their name, please leave blank."
        ),
        required=False,
    )


class RequestDataLicenceForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataRequest
        fields = ['data_licence']

    data_licence = GOVUKDesignSystemTextareaField(
        label="How is the data licensed?",
        help_text=(
            "Provide details of any licence conditions regarding use of the data, "
            "for example Creative Commons Attribution or Open Government Licence, "
            "or restrictions on data scraping."
        ),
    )
