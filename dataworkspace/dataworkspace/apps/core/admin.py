from csp.decorators import csp_update
from django.contrib import admin

from dataworkspace.apps.core.models import (
    Team,
    TeamMembership,
    NewsletterSubscription,
)


class DeletableTimeStampedUserTabularInline(admin.TabularInline):
    exclude = ["created_date", "updated_date", "created_by", "updated_by", "deleted"]


class TimeStampedUserAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class DeletableTimeStampedUserAdmin(TimeStampedUserAdmin):
    exclude = ["created_date", "updated_date", "created_by", "updated_by", "deleted"]

    def get_queryset(self, request):
        # Only show non-deleted models in admin
        return self.model.objects.live()

    def get_actions(self, request):
        """
        Disable bulk delete so tables can be managed.
        :param request:
        :return:
        """
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions


class TeamMembershipAdmin(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ("user",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    readonly_fields = ["schema_name"]
    inlines = (TeamMembershipAdmin,)


class CSPRichTextEditorMixin:

    # We allow inline scripts to run on this page in order to support CKEditor,
    # which gives rich-text formatting but unfortunately uses inline scripts to
    # do so - and we don't have a clean way to either hash the inline script on-demand
    # or inject our request CSP nonce.
    @csp_update(SCRIPT_SRC="'unsafe-inline'")
    def add_view(self, request, form_url="", extra_context=None):
        return super().add_view(request, form_url, extra_context)

    @csp_update(SCRIPT_SRC="'unsafe-inline'")
    def change_view(self, request, object_id, form_url="", extra_context=None):
        return super().change_view(request, object_id, form_url, extra_context)


class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active")

admin.site.register(NewsletterSubscription, NewsletterSubscriptionAdmin)