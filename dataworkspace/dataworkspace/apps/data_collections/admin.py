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
        "created_by",
        "updated_by",
        "dataset",
    )
    readonly_fields = (
        "created_by",
        "updated_by",
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
        "created_by",
        "updated_by",
        "visualisation",
    )
    readonly_fields = (
        "created_by",
        "updated_by",
    )
    fieldsets = [
        (
            None,
            {"fields": ["deleted", "visualisation"]},
        ),
    ]
    ordering = ("visualisation",)


class CollectionAdmin(DeletableTimeStampedUserAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ["name"]
    ordering = ["name"]
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
