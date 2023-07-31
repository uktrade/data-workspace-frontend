from django.contrib import admin
from django.db.models import Count, Q
from dataworkspace.apps.data_collections.forms import (
    CollectionDatasetForm,
    CollectionUserForm,
    CollectionVisualisationForm,
)
from dataworkspace.apps.core.admin import CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin
from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionUserMembership,
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
    form = CollectionDatasetForm
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
    form = CollectionVisualisationForm
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


class CollectionUserItemMembershipInlineAdmin(admin.TabularInline):
    model = CollectionUserMembership
    form = CollectionUserForm
    extra = 1
    autocomplete_fields = ("user",)
    ordering = ["user__email"]
    fieldsets = [
        (
            None,
            {"fields": ["user", "deleted"]},
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted=False)

    def has_delete_permission(self, request, obj=None):
        return False


class CollectionAdmin(CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin):
    exclude = ["created_date", "updated_date", "created_by", "updated_by"]
    list_display = (
        "name",
        "datasets_count",
        "dashboards_count",
        "users_count",
        "notes_added",
        "owner",
        "deleted",
    )
    search_fields = ["name"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "deleted",
                    "name",
                    "description",
                    "owner",
                    "id",
                    "notes",
                    "user_access_type",
                ]
            },
        ),
    ]
    autocomplete_fields = ("owner",)
    readonly_fields = ["id"]
    inlines = (
        CollectionDatasetMembershipInlineAdmin,
        CollectionVisualisationCatalogueItemMembershipInlineAdmin,
        CollectionUserItemMembershipInlineAdmin,
    )

    def get_queryset(self, request):
        return self.model.objects.all().annotate(
            datasets_count=Count(
                "dataset_collections", filter=Q(dataset_collections__deleted=False), distinct=True
            ),
            dashboards_count=Count(
                "visualisation_collections",
                filter=Q(visualisation_collections__deleted=False),
                distinct=True,
            ),
            users_count=Count(
                "user_memberships", filter=Q(user_memberships__deleted=False), distinct=True
            ),
        )


admin.site.register(Collection, CollectionAdmin)
