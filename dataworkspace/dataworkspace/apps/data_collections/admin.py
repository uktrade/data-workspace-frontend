from django.contrib import admin
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin

from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionVisualisationCatalogueItemMembership,
)


class CollectionDatasetMembershipAdmin(admin.TabularInline):
    model = CollectionDatasetMembership
    extra = 1
    autocomplete_fields = (
        "collection",
    )
    fieldsets = [
        (
            None,
            {"fields": ["deleted", "dataset"]},
        ),
    ]


class CollectionVisualisationCatalogueItemMembershipAdmin(admin.TabularInline):
    model = CollectionVisualisationCatalogueItemMembership
    extra = 1
    autocomplete_fields = (
        "collection",
        "visualisation",
    )
    fieldsets = [
        (
            None,
            {"fields": ["deleted", "visualisation"]},
        ),
    ]


class CollectionAdmin(DeletableTimeStampedUserAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ["name"]
    fieldsets = [
        (
            None,
            {"fields": ["name", "description", "owner", "id", "notes"]},
        ),
    ]
    autocomplete_fields = ("owner",)
    readonly_fields = ["id"]
    inlines = (
        CollectionDatasetMembershipAdmin,
        CollectionVisualisationCatalogueItemMembershipAdmin,
    )


admin.site.register(Collection, CollectionAdmin)
