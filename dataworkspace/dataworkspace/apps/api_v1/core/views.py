from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.models import UserSatisfactionSurvey
from dataworkspace.apps.core.utils import (
    new_private_database_credentials,
    postgres_user,
    source_tables_for_user,
    stable_identification_suffix,
)

from dataworkspace.apps.api_v1.core.serializers import UserSatisfactionSurveySerializer


class UserSatisfactionSurveyViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list user satisfaction survey results for ingestion by data flow
    """

    queryset = UserSatisfactionSurvey.objects.all()
    serializer_class = UserSatisfactionSurveySerializer
    pagination_class = PageNumberPagination


credentials_version_key = 'superset_credentials_version'


def get_cached_credentials_key(user_profile_sso_id):
    credentials_version = cache.get(credentials_version_key, None)
    if not credentials_version:
        credentials_version = 1
        cache.set(credentials_version_key, credentials_version)
    return f"superset_credentials_{credentials_version}_{user_profile_sso_id}"


def get_superset_credentials(request):
    cache_key = get_cached_credentials_key(request.headers['sso-profile-user-id'])
    credentials = cache.get(cache_key, None)

    if not credentials:
        dw_user = get_user_model().objects.get(
            profile__sso_id=request.headers['sso-profile-user-id']
        )
        if not dw_user.user_permissions.filter(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists():
            return HttpResponse('Unauthorized', status=401)

        duration = timedelta(hours=24)
        cache_duration = (duration - timedelta(minutes=15)).total_seconds()

        source_tables = source_tables_for_user(dw_user)
        db_role_schema_suffix = stable_identification_suffix(
            str(dw_user.profile.sso_id), short=True
        )
        credentials = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(dw_user.email, suffix='superset'),
            dw_user,
            valid_for=duration,
        )
        cache.set(cache_key, credentials, timeout=cache_duration)

    return JsonResponse(credentials[0])


def remove_superset_user_cached_credentials(user_profile_sso_id):
    cache_key = get_cached_credentials_key(user_profile_sso_id)
    cache.delete(cache_key)


def invalidate_superset_user_cached_credentials():
    credentials_version = cache.get(credentials_version_key, 0)
    with cache.lock(
        'get_superset_credentials_version', blocking_timeout=30, timeout=180,
    ):
        credentials_version += 1
        cache.set(credentials_version_key, credentials_version)
