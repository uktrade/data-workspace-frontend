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
    autocomplete_fields = ("collection", "created_by",)
    ordering = ["dataset"]


class CollectionVisualisationCatalogueItemMembershipAdmin(admin.TabularInline):
    model = CollectionVisualisationCatalogueItemMembership
    extra = 1
    autocomplete_fields = ("collection", "created_by",)
    ordering = ["visualisation"]


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
    readonly_fields = ["id"]
    inlines = (
        CollectionDatasetMembershipAdmin,
        CollectionVisualisationCatalogueItemMembershipAdmin,
    )


admin.site.register(Collection, CollectionAdmin)
