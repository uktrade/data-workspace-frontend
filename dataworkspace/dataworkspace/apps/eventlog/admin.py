import csv
import json
from datetime import datetime

from django.contrib import admin
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.http import HttpResponse
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html

from dataworkspace.apps.eventlog.models import EventLog


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user_link", "event_type", "related_object_link")
    list_filter = ("event_type",)
    list_display_links = ["timestamp"]
    fields = (
        "timestamp",
        "user_link",
        "event_type",
        "related_object_link",
        "event_data",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name")
    actions = ["export_events"]
    list_per_page = 50

    def user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>'.format(
                reverse("admin:auth_user_change", args=(obj.user.id,)),
                obj.user.get_full_name(),
            )
        )

    user_link.short_description = "User"

    def related_object_link(self, obj):
        if obj.related_object is None:
            return None

        try:
            url = reverse(
                admin_urlname(obj.related_object._meta, "change"),
                args=(obj.related_object.id,),
            )
        except NoReverseMatch:
            url = reverse("datasets:dataset_detail", args=(obj.object_id,))

        return format_html(f'<a href="{url}">{obj.related_object}</a>')

    related_object_link.short_description = "Related Object"

    def event_data(self, obj):
        return format_html("<pre>{0}</pre>", json.dumps(obj.extra, indent=2))

    def get_actions(self, request):
        # Disable bulk delete
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def export_events(self, request, queryset):
        field_names = ["timestamp", "user", "event_type", "related_object", "extra"]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=event-log-{}.csv".format(
            datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        writer = csv.DictWriter(response, field_names, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        for eventlog in queryset:
            writer.writerow(
                {
                    "timestamp": eventlog.timestamp,
                    "user": eventlog.user.get_full_name(),
                    "event_type": eventlog.get_event_type_display(),
                    "related_object": eventlog.related_object,
                    "extra": json.dumps(eventlog.extra),
                }
            )
        return response

    export_events.short_description = "Export Selected"
