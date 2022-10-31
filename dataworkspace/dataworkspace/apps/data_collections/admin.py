from django.contrib import admin
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin

from dataworkspace.apps.data_collections.models import Collection, CollectionDatasetMembership


class CollectionDatasetMembershipAdmin(admin.TabularInline):
    model = CollectionDatasetMembership
    extra = 1
    autocomplete_fields = ("collection",)


class CollectionAdmin(DeletableTimeStampedUserAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ["name"]
    fieldsets = [
        (
            None,
            {"fields": ["published", "name", "description", "owner", "id"]},
        ),
    ]
    readonly_fields = ["id"]
    inlines = (CollectionDatasetMembershipAdmin,)


admin.site.register(Collection, CollectionAdmin)
