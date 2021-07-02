from django.conf import settings


def common(request):
    # Ready to add a permissions check. Note: after putting an initial permissions
    # check here, we did occasionally run out of database connections and use
    # 100% CPU on the server. There was some evidence that an exception here
    # caused some sort of infinite loop rending the 500 error page, which caused
    # this function to be called, which then caused another exception...
    #
    # Not sure of cause/effect, but out of paranoia, decided to remove the
    # database query.
    can_see_visualisations_tab = False

    return {
        "root_href": f"{request.scheme}://{settings.APPLICATION_ROOT_DOMAIN}/",
        "can_see_visualisations_tab": can_see_visualisations_tab,
        "gtm_container_id": settings.GTM_CONTAINER_ID,
        "gtm_container_environment_params": settings.GTM_CONTAINER_ENVIRONMENT_PARAMS,
        "CASE_STUDIES_FLAG": settings.CASE_STUDIES_FLAG,
        "NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG": settings.NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG,
        "NOTIFY_ON_DATACUT_CHANGE_FLAG": settings.NOTIFY_ON_DATACUT_CHANGE_FLAG,
        "NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG": settings.NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG,
        "ZENDESK_EMAIL": settings.ZENDESK_EMAIL,
        "TEAMS_DATA_WORKSPACE_COMMUNITY_URL": settings.TEAMS_DATA_WORKSPACE_COMMUNITY_URL,
        "DATA_WORKSPACE_ROADMAP_URL": settings.DATA_WORKSPACE_ROADMAP_URL,
        "SSO_USER_ID": request.META.get("HTTP_SSO_PROFILE_USER_ID", ""),
        "CHART_BUILDER_BUILD_CHARTS_FLAG": settings.CHART_BUILDER_BUILD_CHARTS_FLAG,
        "CHART_BUILDER_PUBLISH_CHARTS_FLAG": settings.CHART_BUILDER_PUBLISH_CHARTS_FLAG,
    }
