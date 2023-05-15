from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model as django_get_user_model

from dataworkspace.apps.api_v1.core.views import remove_superset_user_cached_credentials
from dataworkspace.apps.core.models import get_user_model
from dataworkspace.apps.explorer.schema import clear_schema_info_cache_for_user
from dataworkspace.apps.explorer.utils import (
    remove_data_explorer_user_cached_credentials,
)


def clear_tool_cached_credentials(modeladmin, request, queryset):
    for u in queryset:
        if not isinstance(u, (get_user_model(), django_get_user_model())):
            continue
        remove_data_explorer_user_cached_credentials(u)
        remove_superset_user_cached_credentials(u)
        clear_schema_info_cache_for_user(u)
        modeladmin.message_user(
            request, f"Data Explorer and Superset credentials have been reset for {u}"
        )


clear_tool_cached_credentials.description = "Reset Data Explorer and Superset credentials"


UserAdmin.actions += [clear_tool_cached_credentials]
