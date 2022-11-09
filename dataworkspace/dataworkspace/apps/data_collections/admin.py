from django.contrib import admin
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin

from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionVisualisationCatalogueItemMembership,
)


from dataworkspace.apps.datasets.models import DataSet


# This is only used for autocomplete and is hidden from the admin UI
class AutocompleteDatasetAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted=False)

    def has_module_permission(self, request):
        return False


admin.site.register(
    DataSet,
    AutocompleteDatasetAdmin,
)


class CollectionDatasetMembershipInlineAdmin(admin.TabularInline):
    model = CollectionDatasetMembership
    extra = 1
    autocomplete_fields = ("dataset",)
    ordering = ["dataset__name"]
    fieldsets = [
        (
            None,
            {"fields": ["dataset", "deleted"]},
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted=False)

    def has_delete_permission(self, request, obj=None):
        return False


class CollectionVisualisationCatalogueItemMembershipInlineAdmin(admin.TabularInline):
    model = CollectionVisualisationCatalogueItemMembership
    extra = 1
    autocomplete_fields = ("visualisation",)
    ordering = ["visualisation__name"]
    fieldsets = [
        (
            None,
            {"fields": ["visualisation", "deleted"]},
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted=False)

    def has_delete_permission(self, request, obj=None):
        return False


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
        CollectionDatasetMembershipInlineAdmin,
        CollectionVisualisationCatalogueItemMembershipInlineAdmin,
    )


admin.site.register(Collection, CollectionAdmin)
