from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from dataworkspace.apps.finder.models import DatasetFinderQueryLog


@admin.register(DatasetFinderQueryLog)
class DatasetFinderQueryLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user_link", "query")
    fields = (
        "timestamp",
        "user_link",
        "query",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_per_page = 50

    def user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>'.format(
                reverse("admin:auth_user_change", args=(obj.user.id,)),
                obj.user.get_full_name(),
            )
        )

    user_link.short_description = "User"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
