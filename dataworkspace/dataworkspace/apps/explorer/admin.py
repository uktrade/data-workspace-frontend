from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model

from dataworkspace.apps.explorer.schema import clear_schema_info_cache_for_user
from dataworkspace.apps.explorer.utils import (
    remove_data_explorer_user_cached_credentials,
)


def clear_data_explorer_cached_credentials(modeladmin, request, queryset):
    for u in queryset:
        if not isinstance(u, get_user_model()):
            continue
        remove_data_explorer_user_cached_credentials(u)
        clear_schema_info_cache_for_user(u)
        modeladmin.message_user(
            request, f"Data Explorer credentials have been reset for {u}"
        )


clear_data_explorer_cached_credentials.description = "Reset Data Explorer credentials"


UserAdmin.actions += [clear_data_explorer_cached_credentials]
