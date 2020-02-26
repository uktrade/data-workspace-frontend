from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from dataworkspace.apps.applications.models import ApplicationInstance


def common(request):
    # Although superusers can alway access the Visualisations page itself,
    # during early development, we hide the tab itself from the interface
    # unless the user has been given the explicit permission to develop
    # visualisations. This is so until the interface is a bit more final, most
    # superusers still see the application as most users will, which is good
    # for demos, but can optionally see the WIP interface as needed.
    #
    # This I suspect is _not_ cached, and so results in a database query on
    # every page load. This is slightly unfortunate, but should be acceptable
    # for an easy query.
    can_see_visualisations_tab = request.user.user_permissions.filter(
        codename='develop_visualisations',
        content_type=ContentType.objects.get_for_model(ApplicationInstance),
    ).exists()

    return {
        'root_href': f'{request.scheme}://{settings.APPLICATION_ROOT_DOMAIN}/',
        'google_analytics_site_id': settings.GOOGLE_ANALYTICS_SITE_ID,
        'can_see_visualisations_tab': can_see_visualisations_tab,
        'gtm_container_id': settings.GTM_CONTAINER_ID,
        'gtm_container_environment_params': settings.GTM_CONTAINER_ENVIRONMENT_PARAMS,
    }
