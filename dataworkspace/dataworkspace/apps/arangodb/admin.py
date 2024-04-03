import functools
from django.contrib import admin

from dataworkspace.apps.core.admin import (
    DeletableTimeStampedUserAdmin,
)
from dataworkspace.apps.dw_admin.forms import BaseDatasetForm
from dataworkspace.apps.arangodb.models import (
    ArangoDataset,
    GraphDataSetUserPermission,
    SourceGraphCollection,
)


class GraphDatasetForm(BaseDatasetForm):

    class Meta:
        model = ArangoDataset
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # Pass user defined in ArangoDataset get_form to BaseDatasetForm
        # Note: Currently causes an error on object form change page due to BaseDatasetForm init requirements.
        super().__init__(*args, **kwargs)
    

@admin.register(ArangoDataset)
class GraphDatasetAdmin(DeletableTimeStampedUserAdmin, admin.ModelAdmin):

    form = GraphDatasetForm
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                    "slug",
                    "short_description",
                    "information_asset_owner",
                    "information_asset_manager",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "user_access_type",
                    "eligibility_criteria",
                    "authorized_email_domains",
                    "authorized_users",
                    "request_approvers",
                ]
            },
        ),
    ]

    class Media:
        js = ("js/min/django_better_admin_arrayfield.min.js",)
        css = {
            "all": (
                "css/min/django_better_admin_arrayfield.min.css",
                "data-workspace-admin.css",
            )
        }

    def get_form(self, request, obj=None, **kwargs):  
        form_class = super().get_form(request, obj=None, **kwargs)
        return functools.partial(form_class, user=request.user)
    

@admin.register(GraphDataSetUserPermission)
class GraphDataSetUserPermissionAdmin(admin.ModelAdmin):
    # TEMPORARY: Register User Permission Model for Testing Connection

    class Meta:
        fields = ("user", "collection")
        model = GraphDataSetUserPermission


@admin.register(SourceGraphCollection)
class SourceGraphCollectionAdmin(admin.ModelAdmin):
    # TEMPORARY: Register Source Collection Model for Testing Connection

    class Meta:
        fields = ("graph_dataset", "reference_number")
        model = SourceGraphCollection
