import os

from superset.security import SupersetSecurityManager
from flask_appbuilder.security.manager import AUTH_REMOTE_USER
from flask_appbuilder.security.views import AuthView
from flask_login import login_user
from flask_appbuilder import expose

# Semi-magical request-local proxy objects
from flask import g, make_response, redirect, request

SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{os.environ["DB_USER"]}:{os.environ["DB_PASSWORD"]}@{os.environ["DB_HOST"]}/{os.environ["DB_NAME"]}'
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


class DataWorkspaceRemoteUserView(AuthView):
    @expose('/login/')
    def login(self):
        role_name = base_role_names[request.host.split('.')[0]]

        # If user already logged in, redirect to index...
        if g.user is not None and g.user.is_authenticated:
            return redirect(self.appbuilder.get_url_for_index)

        app = self.appbuilder.get_app
        if role_name == 'Admin':
            is_admin = (
                request.environ["HTTP_SSO_PROFILE_EMAIL"] in app.config['ADMIN_USERS']
            )
            if not is_admin:
                return make_response({}, 401)

        security_manager = self.appbuilder.sm
        username = f'{request.environ["HTTP_SSO_PROFILE_USER_ID"]}--{role_name}'
        email_parts = request.environ["HTTP_SSO_PROFILE_EMAIL"].split('@')
        email_parts[0] += f'+{role_name.lower()}'
        email = '@'.join(email_parts)

        # ... else if user exists but not logged in, update details, log in, and redirect to index
        user = security_manager.find_user(username=username)
        if user is not None:
            user.first_name = request.environ["HTTP_SSO_PROFILE_FIRST_NAME"]
            user.last_name = (
                f'{request.environ["HTTP_SSO_PROFILE_LAST_NAME"]} ({role_name})'
            )
            user.email = email
            security_manager.update_user(user)
            login_user(user)
            return redirect(self.appbuilder.get_url_for_index)

        # ... else create user, login, and redirect to index
        user = security_manager.add_user(
            username=username,
            first_name=request.environ["HTTP_SSO_PROFILE_FIRST_NAME"],
            last_name=f'{request.environ["HTTP_SSO_PROFILE_LAST_NAME"]} ({role_name})',
            email=email,
            role=security_manager.find_role(role_name),
        )
        login_user(user)
        return redirect(self.appbuilder.get_url_for_index)


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


CUSTOM_SECURITY_MANAGER = DataWorkspaceSecurityManager
AUTH_TYPE = AUTH_REMOTE_USER
