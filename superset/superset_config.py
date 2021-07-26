import decimal
import os

from flask_appbuilder.security.manager import AUTH_REMOTE_USER
from flask_appbuilder.security.views import AuthView
from flask_appbuilder import expose
from flask_login import login_user

from werkzeug.middleware.proxy_fix import ProxyFix

# Semi-magical request-local proxy objects
from flask import g, json, make_response, redirect, request

from superset import db, security_manager
from superset.security import SupersetSecurityManager

SQLALCHEMY_DATABASE_URI = (
    f'postgresql+psycopg2://{os.environ["DB_USER"]}:{os.environ["DB_PASSWORD"]}'
    f'@{os.environ["DB_HOST"]}/{os.environ["DB_NAME"]}'
)

LANGUAGES = {'en': {'flag': 'gb', 'name': 'English'}}
SESSION_COOKIE_NAME = 'superset_session'

ADMIN_USERS = os.environ['ADMIN_USERS'].split(',')
SECRET_KEY = 'secret'
UPLOAD_FOLDER = '/tmp/superset-uploads/'

base_role_names = {
    'superset': 'Public',
    'superset-edit': 'Editor',
    'superset-admin': 'Admin',
}

PUBLIC_ROLE_PERMISSIONS = [
    ('can_csrf_token', 'Superset'),
    ('can_dashboard', 'Superset'),
    ('can_explore', 'Superset'),
    ('can_explore_json', 'Superset'),
    ('can_fave_dashboards', 'Superset'),
    ('can_favstar', 'Superset'),
    ('can_list', 'CssTemplateAsyncModelView'),
    ('can_list', 'Dashboard'),
    ('can_log', 'Superset'),
    ('can_read', 'Annotation'),
    ('can_read', 'Chart'),
    ('can_read', 'CssTemplate'),
    ('can_read', 'Dashboard'),
    ('can_read', 'Dataset'),
    ('can_read', 'Log'),
    ('can_read', 'Query'),
    ('can_read', 'SavedQuery'),
    ('can_recent_activity', 'Superset'),
    ('can_show', 'CssTemplateAsyncModelView'),
    ('can_slice', 'Superset'),
    ('can_warm_up_cache', 'Superset'),
]


class DataWorkspaceRemoteUserView(AuthView):
    @expose('/login/')
    def login(self):
        role_name = base_role_names[request.host.split('.')[0]]
        username = f'{request.environ["HTTP_SSO_PROFILE_USER_ID"]}--{role_name}'
        email_parts = request.environ["HTTP_SSO_PROFILE_EMAIL"].split('@')
        email_parts[0] += f'+{role_name.lower()}'
        email = '@'.join(email_parts)

        # If user already logged in, redirect to index...
        if g.user is not None and g.user.is_authenticated:
            return redirect(self.appbuilder.get_url_for_index)

        app = self.appbuilder.get_app

        if role_name == 'Admin':
            is_admin = request.headers["Sso-Profile-Email"] in app.config['ADMIN_USERS']
            if not is_admin:
                return make_response({}, 401)

        # ... else if user exists but not logged in, update details, log in, and redirect to index
        user = security_manager.find_user(username=username)
        if user is not None:
            user.first_name = request.headers["Sso-Profile-First-Name"]
            user.last_name = f'{request.headers["Sso-Profile-Last-Name"]} ({role_name})'
            user.email = email
            security_manager.update_user(user)
            login_user(user)
            return redirect(self.appbuilder.get_url_for_index)

        # ... else create user, login, and redirect to index
        user = security_manager.add_user(
            username=username,
            first_name=request.headers["Sso-Profile-First-Name"],
            last_name=f'{request.headers["Sso-Profile-Last-Name"]} ({role_name})',
            email=email,
            role=security_manager.find_role(role_name),
        )

        if not user:
            return make_response(
                f'Unable to find or create a user with role {role_name}', 500
            )

        login_user(user)
        return redirect(self.appbuilder.get_url_for_index)


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

    # Delete permissions to existing dashboards
    delete_datasource_perms(sm, role)

    # Add permissions for datasources in dashboards that the user has access to
    for dashboard_id in request.headers['Dashboards'].split(','):
        if not dashboard_id:
            continue
        dashboard = db.session.query(Dashboard).get(dashboard_id)
        if dashboard is not None:
            for datasource in dashboard.slices:
                permission_view_menu = sm.add_permission_view_menu(
                    'datasource_access', datasource.perm
                )
                sm.add_permission_role(role, permission_view_menu)

    user.roles.append(role)
    sm.get_session.commit()


def apply_datasource_perm(sm, role, datasource):
    """
    Give the specified role access to the specified datasource
    """
    permission_view_menu = sm.add_permission_view_menu(
        'datasource_access', datasource.perm
    )
    sm.add_permission_role(role, permission_view_menu)


def delete_datasource_perms(sm, role):
    for perm in role.permissions:
        if perm.permission.name == 'datasource_access':
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
    for datasource in db.session.query(Slice).filter(
        Slice.owners.any(sm.user_model.id.in_([user.get_id()]))
    ):
        apply_datasource_perm(sm, role, datasource)

    # Give users access to any datasets they are owners of
    for table in db.session.query(SqlaTable).filter(
        SqlaTable.owners.any(  # pylint: disable=no-member
            sm.user_model.id.in_([user.get_id()])
        )
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
            db.session.add(table)

    user.roles.append(role)
    sm.get_session.commit()


def app_mutator(app):
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):  # pylint: disable=arguments-differ
            if isinstance(obj, decimal.Decimal):
                return str(obj)
            return super().default(obj)

    with app.app_context():
        app.json_encoder = CustomJSONEncoder

    @app.before_request
    def before_request():  # pylint: disable=unused-variable
        if g.user is not None and g.user.is_authenticated:
            role_name = base_role_names[request.host.split('.')[0]]
            if role_name == 'Public':
                apply_public_role_permissions(
                    security_manager, g.user, f'{g.user.username}-Role'
                )
            elif role_name == 'Editor':
                apply_editor_role_permissions(
                    security_manager, g.user, f'{g.user.username}-Role'
                )


class DataWorkspaceSecurityManager(SupersetSecurityManager):
    # The Flask AppBuilder Security Manager, from which the Superset Security Manager
    # inherits, uses this if AUTH_TYPE == AUTH_REMOTE_USER
    authremoteuserview = DataWorkspaceRemoteUserView


def DB_CONNECTION_MUTATOR(uri, params, username, security_manager, source):
    uri.host = request.headers['Credentials-Db-Host']
    uri.username = request.headers['Credentials-Db-User']
    uri.database = request.headers['Credentials-Db-Name']
    uri.password = request.headers['Credentials-Db-Password']
    uri.port = request.headers['Credentials-Db-Port']
    return uri, params


FLASK_APP_MUTATOR = app_mutator
CUSTOM_SECURITY_MANAGER = DataWorkspaceSecurityManager
AUTH_TYPE = AUTH_REMOTE_USER
ADDITIONAL_MIDDLEWARE = [lambda app: ProxyFix(app, x_proto=1)]

FEATURE_FLAGS = {'SQLLAB_BACKEND_PERSISTENCE': True}
