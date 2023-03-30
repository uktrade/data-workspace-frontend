from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.api_v1.core.serializers import (
    UserSatisfactionSurveySerializer,
    NewsletterSubscriptionSerializer,
    TeamSerializer,
)
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.models import UserSatisfactionSurvey, NewsletterSubscription, Team, TeamMembership
from dataworkspace.apps.core.utils import (
    generate_jwt_token,
    new_private_database_credentials,
    postgres_user,
    source_tables_for_user,
    stable_identification_suffix,
)
from dataworkspace.apps.datasets.models import VisualisationLink


class UserSatisfactionSurveyViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list user satisfaction survey results for ingestion by data flow
    """

    queryset = UserSatisfactionSurvey.objects.all()
    serializer_class = UserSatisfactionSurveySerializer
    pagination_class = PageNumberPagination


credentials_version_key = "superset_credentials_version"


def get_cached_credentials_key(user_profile_sso_id, endpoint):
    # Set to never expire as reverting to a previous version will cause
    # potentially invalid cached credentials to be used if the user loses
    # or gains access to a dashboard
    cache.set(credentials_version_key, 1, nx=True, timeout=None)
    credentials_version = cache.get(credentials_version_key, None)
    return f"superset_credentials_{credentials_version}_{endpoint}_{user_profile_sso_id}"


def get_superset_credentials(request):
    superset_endpoint = {
        urlparse(url).netloc: name for name, url in settings.SUPERSET_DOMAINS.items()
    }[request.headers["host"]]

    cache_key = get_cached_credentials_key(
        request.headers["sso-profile-user-id"], superset_endpoint
    )
    response = cache.get(cache_key, None)
    if not response:
        dw_user = get_user_model().objects.get(
            profile__sso_id=request.headers["sso-profile-user-id"]
        )
        if not dw_user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists():
            return HttpResponse("Unauthorized", status=401)

        duration = timedelta(hours=24)
        cache_duration = (duration - timedelta(minutes=15)).total_seconds()

        # Give "public" users full db credentials
        if superset_endpoint == "view":
            dashboards_user_can_access = [
                d.identifier
                for d in VisualisationLink.objects.filter(visualisation_type="SUPERSET")
                if d.visualisation_catalogue_item.user_has_access(dw_user)
            ]
            credentials = [
                {
                    "memorable_name": alias,
                    "db_name": data["NAME"],
                    "db_host": data["HOST"],
                    "db_port": data["PORT"],
                    "db_user": data["USER"],
                    "db_password": data["PASSWORD"],
                }
                for alias, data in settings.DATABASES_DATA.items()
            ]

        # Give "editor"/"admin" users temp private credentials
        else:
            dashboards_user_can_access = []
            source_tables = source_tables_for_user(dw_user)
            db_role_schema_suffix = stable_identification_suffix(
                str(dw_user.profile.sso_id), short=True
            )
            credentials = new_private_database_credentials(
                db_role_schema_suffix,
                source_tables,
                postgres_user(dw_user.email, suffix="superset"),
                dw_user,
                valid_for=duration,
            )

        response = {
            "credentials": credentials[0],
            "dashboards": dashboards_user_can_access,
        }

        cache.set(cache_key, response, timeout=cache_duration)

    return JsonResponse(response)


def remove_superset_user_cached_credentials(user):
    for domain in settings.SUPERSET_DOMAINS.keys():
        cache_key = get_cached_credentials_key(user.profile.sso_id, domain)
        cache.delete(cache_key)


def invalidate_superset_user_cached_credentials():
    credentials_version = cache.get(credentials_version_key, None)
    if credentials_version:
        cache.incr(credentials_version_key)


def generate_mlflow_jwt(request):
    user = get_user_model().objects.get(profile__sso_id=request.headers["sso-profile-user-id"])
    authorised_hosts = list(
        user.authorised_mlflow_instances.all().values_list("instance__hostname", flat=True)
    )
    sub = user.email
    jwt = generate_jwt_token(authorised_hosts, sub)
    return JsonResponse({"jwt": jwt})


class NewsletterSubscriptionViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list newsletter subscriptions for ingestion by data flow
    """

    queryset = NewsletterSubscription.objects.all()
    serializer_class = NewsletterSubscriptionSerializer
    pagination_class = PageNumberPagination
class TeamViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list of team schema members for ingestion by data flow
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    pagination_class = PageNumberPagination
