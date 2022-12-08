from django.contrib import admin
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
    list_display = ("name", "description", "owner", "deleted")
    search_fields = ["name"]
    fieldsets = [
        (
            None,
            {"fields": ["deleted", "name", "description", "owner", "id", "notes"]},
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
        return self.model.objects.all()


admin.site.register(Collection, CollectionAdmin)
