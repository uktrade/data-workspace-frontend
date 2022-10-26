from django.contrib import admin
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin

from dataworkspace.apps.data_collections.models import Collection


class CollectionAdmin(DeletableTimeStampedUserAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ["name"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "published",
                    "name",
                    "description",
                    "owner",
                    "slug",
                ]
            },
        ),
    ]
    readonly_fields = ["slug"]


admin.site.register(Collection, CollectionAdmin)
