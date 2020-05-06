import os

from superset.security import SupersetSecurityManager
from flask_appbuilder.security.manager import AUTH_REMOTE_USER
from flask_appbuilder.security.views import AuthView
from flask_login import login_user
from flask_appbuilder import expose

# Semi-magical request-local proxy objects
from flask import g, request
from flask import redirect

ENABLE_PROXY_FIX = True
SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{os.environ["DB_USER"]}:{os.environ["DB_PASSWORD"]}@{os.environ["DB_HOST"]}/{os.environ["DB_NAME"]}'
LANGUAGES = {'en': {'flag': 'gb', 'name': 'English'}}
SESSION_COOKIE_NAME = 'superset_session'

ADMIN_USERS = os.environ['ADMIN_USERS'].split(',')
SECRET_KEY = os.environ['SECRET_KEY']
UPLOAD_FOLDER = '/tmp/superset-uploads/'


class DataWorkspaceRemoteUserView(AuthView):
    @expose('/login/')
    def login(self):
        # If user already logged in, redirect to index...
        if g.user is not None and g.user.is_authenticated:
            return redirect(self.appbuilder.get_url_for_index)

        security_manager = self.appbuilder.sm
        username = request.environ['HTTP_SSO_PROFILE_USER_ID']

        # ... else if user exists but not logged in, log in, and redirect to index
        user = security_manager.find_user(username=username)
        if user is not None:
            login_user(user)
            return redirect(self.appbuilder.get_url_for_index)

        # ... else create user, login, and redirect to index
        app = self.appbuilder.get_app
        is_admin = (
            request.environ['HTTP_SSO_PROFILE_EMAIL'] in app.config['ADMIN_USERS']
        )
        admin_role = app.config['AUTH_ROLE_ADMIN']
        public_role = app.config['AUTH_ROLE_PUBLIC']

        user = security_manager.add_user(
            username=username,
            first_name=request.environ['HTTP_SSO_PROFILE_FIRST_NAME'],
            last_name=request.environ['HTTP_SSO_PROFILE_LAST_NAME'],
            email=request.environ['HTTP_SSO_PROFILE_EMAIL'],
            role=security_manager.find_role(admin_role if is_admin else public_role),
        )
        login_user(user)
        return redirect(self.appbuilder.get_url_for_index)


class DataWorkspaceSecurityManager(SupersetSecurityManager):
    # The Flask AppBuilder Security Manager, from which the Superset Security Manager
    # inherits, uses this if AUTH_TYPE == AUTH_REMOTE_USER
    authremoteuserview = DataWorkspaceRemoteUserView


CUSTOM_SECURITY_MANAGER = DataWorkspaceSecurityManager
AUTH_TYPE = AUTH_REMOTE_USER
