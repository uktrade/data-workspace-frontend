import logging

from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.core.views import (
    CreateTableDAGStatusView,
    CreateTableDAGTaskStatusView,
    RestoreTableDAGTaskStatusView,
    TechnicalSupportView,
    about_page_view,
    public_error_500_application_view,
    welcome_page_view,
    public_error_403_csrf_html_view,
    public_error_403_html_view,
    public_error_403_invalid_tool_user_html_view,
    public_error_403_tool_permission_denied_html_view,
    public_error_403_visualisation_html_view,
    public_error_404_html_view,
    public_error_500_html_view,
    healthcheck_view,
    SupportView,
    NewsletterSubscriptionView,
    table_data_view,
    UserSatisfactionSurveyView,
    ServeS3UploadedFileView,
    ContactUsView,
)
from dataworkspace.apps.datasets.views import home_view
from dataworkspace.apps.appstream.views import (
    appstream_view,
    appstream_admin_view,
    appstream_restart,
    appstream_fleetstatus,
)

logger = logging.getLogger("app")

admin.autodiscover()
admin.site.site_header = "Data Workspace"
admin.site.login = login_required(admin.site.login)

urlpatterns = [
    path("", login_required(home_view), name="root"),
    path("about/", login_required(about_page_view), name="about"),
    path("welcome/", login_required(welcome_page_view), name="welcome"),
    path("error_403", public_error_403_html_view),
    path("error_403_visualisation", public_error_403_visualisation_html_view),
    path("error_403_csrf", public_error_403_csrf_html_view),
    path("error_403_tool_access", public_error_403_tool_permission_denied_html_view),
    path("error_403_tool_invalid", public_error_403_invalid_tool_user_html_view),
    path("error_404", public_error_404_html_view),
    path("error_500", public_error_500_html_view),
    path("error_500_application", public_error_500_application_view),
    path("appstream/", login_required(appstream_view), name="appstream"),
    path("appstream-admin/", login_required(appstream_admin_view), name="appstream_admin"),
    path(
        "appstream-restart/",
        login_required(appstream_restart),
        name="appstream_restart",
    ),
    path(
        "appstream-admin/fleetstatus",
        appstream_fleetstatus,
        name="appstream_fleetstatus",
    ),
    path(
        "tools/",
        include(
            ("dataworkspace.apps.applications.urls", "applications"),
            namespace="applications",
        ),
    ),
    path(
        "visualisations/",
        include(
            ("dataworkspace.apps.applications.urls_visualisations", "visualisations"),
            namespace="visualisations",
        ),
    ),
    path(
        "catalogue/",
        include(("dataworkspace.apps.catalogue.urls", "catalogue"), namespace="catalogue"),
    ),
    path(
        "datasets/",
        include(("dataworkspace.apps.datasets.urls", "datasets"), namespace="datasets"),
    ),
    path(
        "data-explorer/",
        include(("dataworkspace.apps.explorer.urls", "explorer"), namespace="explorer"),
    ),
    path(
        "request-data/",
        include(
            ("dataworkspace.apps.request_data.urls", "request_data"),
            namespace="request-data",
        ),
    ),
    path(
        "request-access/",
        include(
            ("dataworkspace.apps.request_access.urls", "request_access"),
            namespace="request-access",
        ),
    ),
    path(
        "files/",
        include(
            ("dataworkspace.apps.your_files.urls", "your_files"),
            namespace="your-files",
        ),
    ),
    path("healthcheck", healthcheck_view),  # No authentication
    path("support-and-feedback/", login_required(SupportView.as_view()), name="support"),
    path(
        "support/success/<str:ticket_id>",
        login_required(SupportView.as_view()),
        name="support-success",
    ),
    path(
        "support/technical/",
        login_required(TechnicalSupportView.as_view()),
        name="technical-support",
    ),
    path("contact-us/", login_required(ContactUsView.as_view()), name="contact-us"),
    path(
        "feedback/",
        login_required(UserSatisfactionSurveyView.as_view()),
        name="feedback",
    ),
    path(
        "newsletter_subscription/",
        login_required(NewsletterSubscriptionView.as_view()),
        name="newsletter_subscription",
    ),
    path(
        "case-studies/",
        include(
            ("dataworkspace.apps.case_studies.urls", "case_studies"),
            namespace="case-studies",
        ),
    ),
    path(
        "media",
        login_required(ServeS3UploadedFileView.as_view()),
        name="uploaded-media",
    ),
    path(
        "table_data/<str:database>/<str:schema>/<str:table>",
        login_required(table_data_view),
        name="table_data",
    ),
    path(
        "api/v1/",
        include(("dataworkspace.apps.api_v1.urls", "api_v1"), namespace="api-v1"),
    ),
    path(
        "api/v2/",
        include(("dataworkspace.apps.api_v2.urls", "api_v2"), namespace="api-v2"),
    ),
    path(
        "admin/",
        include(("dataworkspace.apps.dw_admin.urls", "dw_admin"), namespace="dw-admin"),
    ),
    path("admin/", admin.site.urls),
    path(
        "pipelines/",
        include(("dataworkspace.apps.datasets.pipelines.urls", "datasets"), namespace="pipelines"),
    ),
    path(
        "collections/",
        include(
            ("dataworkspace.apps.data_collections.urls", "data_collections"),
            namespace="data_collections",
        ),
    ),
    path(
        "dataflow/dag-status/<str:execution_date>",
        login_required(CreateTableDAGStatusView.as_view()),
        name="create-table-dag-status",
    ),
    path(
        "create-table/status/<str:execution_date>/<str:task_id>",
        login_required(CreateTableDAGTaskStatusView.as_view()),
        name="create-table-task-status",
    ),
    path(
        "restore-table/status/<str:execution_date>/<str:task_id>",
        login_required(RestoreTableDAGTaskStatusView.as_view()),
        name="restore-table-task-status",
    ),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import (  # pylint: disable=ungrouped-imports
        staticfiles_urlpatterns,
    )

    urlpatterns += staticfiles_urlpatterns()

    import debug_toolbar

    urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))

handler403 = public_error_403_html_view
handler404 = public_error_404_html_view
handler500 = public_error_500_html_view
