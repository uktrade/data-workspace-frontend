from django.contrib import admin
from dataworkspace.apps.data_collections.models import Collection


class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ["name"]


admin.site.register(Collection, CollectionAdmin)
