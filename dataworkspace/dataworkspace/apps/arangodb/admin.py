from django.contrib import admin
from dataworkspace.apps.arangodb.models import (
    ArangoTeamMembership,
    ArangoTeam,
)


class ArangoTeamMembershipAdmin(admin.TabularInline):
    model = ArangoTeamMembership
    extra = 1
    autocomplete_fields = ("user",)


@admin.register(ArangoTeam)
class ArangoTeamAdmin(admin.ModelAdmin):
    readonly_fields = ["database_name"]
    inlines = (ArangoTeamMembershipAdmin,)
