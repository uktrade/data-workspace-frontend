import decimal
import os

import sentry_sdk
from flask_appbuilder.models.generic.filters import FilterStartsWith
from flask_appbuilder.security.manager import AUTH_REMOTE_USER
from flask_appbuilder.security.views import AuthView
from flask_appbuilder import expose
from flask_login import login_user
from sentry_sdk.integrations.flask import FlaskIntegration

from werkzeug.middleware.proxy_fix import ProxyFix

# Semi-magical request-local proxy objects
from flask import g, json, make_response, redirect, request, session

from superset import db, security_manager
from superset.security import SupersetSecurityManager

SQLALCHEMY_DATABASE_URI = (
    f'postgresql+psycopg2://{os.environ["DB_USER"]}:{os.environ["DB_PASSWORD"]}'
    f'@{os.environ["DB_HOST"]}/{os.environ["DB_NAME"]}'
)

LANGUAGES = {"en": {"flag": "gb", "name": "English"}}
SESSION_COOKIE_NAME = "superset_session"

ADMIN_USERS = os.environ["ADMIN_USERS"].split(",")
SECRET_KEY = "secret"
UPLOAD_FOLDER = "/tmp/superset-uploads/"

base_role_names = {
    "superset": "Public",
    "superset-edit": "Editor",
    "superset-admin": "Admin",
}

PUBLIC_ROLE_PERMISSIONS = [
    ("can_csrf_token", "Superset"),
    ("can_dashboard", "Superset"),
    ("can_explore_json", "Superset"),
    ("can_favstar", "Superset"),
    ("can_log", "Superset"),
    ("can_read", "Annotation"),
    ("can_read", "Chart"),
    ("can_read", "CssTemplate"),
    ("can_read", "Dashboard"),
    ("can_warm_up_cache", "Superset"),
]


class DataWorkspaceRemoteUserView(AuthView):
    @expose("/login/")
    def login(self):
        role_name = base_role_names[request.host.split(".")[0]]
        username = f'{request.environ["HTTP_SSO_PROFILE_USER_ID"]}--{role_name}'
        email_parts = request.environ["HTTP_SSO_PROFILE_EMAIL"].split("@")
        email_parts[0] += f"+{role_name.lower()}"
        email = "@".join(email_parts)

        redirect_url = request.args.get("next", self.appbuilder.get_url_for_index)

        # If user already logged in, redirect to index...
        if g.user is not None and g.user.is_authenticated:
            return redirect(redirect_url)

        app = self.appbuilder.get_app

        if role_name == "Admin":
            is_admin = request.headers["Sso-Profile-Email"] in app.config["ADMIN_USERS"]
            if not is_admin:
                return make_response({}, 401)

        # In flask, when a user is not authenticated or lacks permissions for a page they
        # they are redirected (to either the index or login page), and a flash message is added
        # to the session saying "Access is denied".
        # So, in the case when a public (unauthed) DW user tries to view a DW embedded dashboard,
        # they will be redirected to this login flow and flask will add the access denied
        # message to their session. There is no easy way around this so in this specific
        # case clear the message queue before the public user is redirected to the dashboard
        if (
            role_name == "Public"
            and redirect_url != self.appbuilder.get_url_for_index
            and "_flashes" in session
        ):
            session["_flashes"].clear()

        # ... else if user exists but not logged in, update details, log in, and redirect to index
        user = security_manager.find_user(username=username)
        if user is not None:
            user.first_name = request.headers["Sso-Profile-First-Name"]
            user.last_name = f'{request.headers["Sso-Profile-Last-Name"]} ({role_name})'
            user.email = email
            security_manager.update_user(user)
            login_user(user)
            return redirect(redirect_url)

        # ... else create user, login, and redirect to index
        user = security_manager.add_user(
            username=username,
            first_name=request.headers["Sso-Profile-First-Name"],
            last_name=f'{request.headers["Sso-Profile-Last-Name"]} ({role_name})',
            email=email,
            role=security_manager.find_role(role_name),
        )

        if not user:
            return make_response(f"Unable to find or create a user with role {role_name}", 500)

        login_user(user)
        return redirect(redirect_url)


def apply_public_role_permissions(sm, user, role_name):
    """
    Given a user and role name
    1. Get or create a private role for the user
    2. Assign minimum level of permissions to the role
    3. Give user read access to all data sources
        - This allows them to view all dashboards on the site
    """
    from superset.models.dashboard import (  # pylint: disable=import-outside-toplevel
        Dashboard,
    )

    role = sm.add_role(role_name)
    if not role:
        role = sm.find_role(role_name)

    for perm in PUBLIC_ROLE_PERMISSIONS:
        permission_view_menu = sm.find_permission_view_menu(perm[0], perm[1])
        sm.add_permission_role(role, permission_view_menu)

    # Add permissions for datasources in dashboards that the user has access to
    datasource_perms = []
    for dashboard_id in request.headers["Dashboards"].split(","):
        if not dashboard_id:
            continue
        dashboard = db.session.query(Dashboard).get(dashboard_id)  # pylint: disable=no-member
        if dashboard is not None:
            for datasource in dashboard.slices:
                permission_view_menu = sm.add_permission_view_menu(
                    "datasource_access", datasource.perm
                )
                if permission_view_menu not in role.permissions:
                    sm.add_permission_role(role, permission_view_menu)
                datasource_perms.append(permission_view_menu)

    # Remove any permissions for dashboards that were not passed in via headers
    for perm in role.permissions:
        if perm.permission.name == "datasource_access" and perm not in datasource_perms:
            sm.del_permission_role(role, perm)

    user.roles.append(role)
    sm.get_session.commit()


def apply_datasource_perm(sm, role, datasource):
    """
    Give the specified role access to the specified datasource
    """
    permission_view_menu = sm.add_permission_view_menu("datasource_access", datasource.perm)
    sm.add_permission_role(role, permission_view_menu)


def delete_datasource_perms(sm, role):
    for perm in role.permissions:
        if perm.permission.name == "datasource_access":
            sm.del_permission_role(role, perm)


def apply_editor_role_permissions(sm, user, role_name):
    """
    Given a user and role name
    1. Get or create a private "editor" role for the user
    2. Give the private editor role access to all datasources the user has created
      - This allows us to restrict the datasources/charts the user can see to only those they created
    """
    from superset.models.slice import Slice  # pylint: disable=import-outside-toplevel
    from superset.connectors.sqla.models import (  # pylint: disable=import-outside-toplevel
        SqlaTable,
    )

    role = sm.add_role(role_name)
    if not role:
        role = sm.find_role(role_name)

    # Delete any existing perms attached to this user's role
    delete_datasource_perms(sm, role)

    # Give users access to any slices they are owners of
    for datasource in db.session.query(Slice).filter(  # pylint: disable=no-member
        Slice.owners.any(sm.user_model.id.in_([user.get_id()]))
    ):
        apply_datasource_perm(sm, role, datasource)

    # Give users access to any datasets they are owners of
    for table in db.session.query(SqlaTable).filter(  # pylint: disable=no-member
        SqlaTable.owners.any(sm.user_model.id.in_([user.get_id()]))  # pylint: disable=no-member
    ):
        apply_datasource_perm(sm, role, table)

        # By default "virtual" datasets are flagged and filtered out of the chart creation
        # forms without any indication. The argument for this was...
        # "it may be a bit confusing, but certainly less than seeing lots of user generated views."
        # As we only allow users to see the "views" they have created this does not work for us.
        # So here we remove the flag so users can create charts with virtual datasets as
        # if they were tables.
        if table.is_sqllab_view:
            table.is_sqllab_view = False
            db.session.add(table)  # pylint: disable=no-member

    user.roles.append(role)
    sm.get_session.commit()


def app_mutator(app):
    from superset.views import (  # pylint: disable=import-outside-toplevel
        filters,
        base_api,
    )

    # Monkey patch the related owners filter to remove any non-editor users
    class FilterRelatedOwners(filters.FilterRelatedOwners):
        def apply(self, query, value):
            user_model = security_manager.user_model
            query = query.filter(user_model.username.ilike("%editor%"))
            return super().apply(query, value)

    filters.FilterRelatedOwners = FilterRelatedOwners

    # Override related user view filters to force the filters to be added even if
    # there is no filter value. This is necessary to allow us to filter
    # out non-editor users on every request, even if there is no value to filter
    # for (i.e. filter = '')
    class BaseSupersetModelRestApi(base_api.BaseSupersetModelRestApi):
        def _get_related_filter(self, datamodel, column_name, value):
            filter_field = self.related_field_filters.get(column_name)
            if isinstance(filter_field, str):
                filter_field = (
                    base_api.RelatedFieldFilter(  # pylint: disable=self-assigning-variable
                        str(filter_field), FilterStartsWith
                    )
                )
            search_columns = [filter_field.field_name] if filter_field else None
            filters = datamodel.get_filters(search_columns)
            if base_filters := self.base_related_field_filters.get(column_name):
                filters.add_filter_list(base_filters)
            if base_filters:
                filters.add_filter_list(base_filters)
            if filter_field:
                # If filtering for related owners ensure we always run the
                # filter even if the value we're filtering for is ''. This allows
                # us to always filter out non-editor users.
                if filter_field.filter_class == FilterRelatedOwners:
                    filters.add_filter(
                        filter_field.field_name,
                        filter_field.filter_class,
                        value if value else "",
                    )
                # Any non-related-owner filters are handled as usual
                elif value:
                    filters.add_filter(
                        filter_field.field_name,
                        filter_field.filter_class,
                        value,
                    )

            return filters

    base_api.BaseSupersetModelRestApi = BaseSupersetModelRestApi

    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, o):  # pylint: disable=arguments-differ
            if isinstance(o, decimal.Decimal):
                return str(o)
            return super().default(o)

    with app.app_context():
        app.json_encoder = CustomJSONEncoder

    @app.before_request
    def before_request():  # pylint: disable=unused-variable
        if g.user is not None and g.user.is_authenticated:
            role_name = base_role_names[request.host.split(".")[0]]
            if role_name == "Public":
                apply_public_role_permissions(security_manager, g.user, f"{g.user.username}-Role")
            elif role_name == "Editor":
                apply_editor_role_permissions(security_manager, g.user, f"{g.user.username}-Role")


class DataWorkspaceSecurityManager(SupersetSecurityManager):
    # The Flask AppBuilder Security Manager, from which the Superset Security Manager
    # inherits, uses this if AUTH_TYPE == AUTH_REMOTE_USER
    authremoteuserview = DataWorkspaceRemoteUserView


def DB_CONNECTION_MUTATOR(uri, params, username, security_manager, source):
    if "Credentials-Db-Host" in request.headers:
        uri = uri._replace(
            host=request.headers["Credentials-Db-Host"],
            username=request.headers["Credentials-Db-User"],
            database=request.headers["Credentials-Db-Name"],
            password=request.headers["Credentials-Db-Password"],
            port=request.headers["Credentials-Db-Port"],
        )
    return uri, params


FLASK_APP_MUTATOR = app_mutator
CUSTOM_SECURITY_MANAGER = DataWorkspaceSecurityManager
AUTH_TYPE = AUTH_REMOTE_USER
ADDITIONAL_MIDDLEWARE = [lambda app: ProxyFix(app, x_proto=1)]

FEATURE_FLAGS = {"SQLLAB_BACKEND_PERSISTENCE": True}

if os.environ.get("SENTRY_DSN") is not None:
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        integrations=[FlaskIntegration()],
    )
