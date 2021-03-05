print("START OF CONFIG")
import os

from superset.security import SupersetSecurityManager
from flask_appbuilder.security.manager import AUTH_REMOTE_USER
from flask_appbuilder.security.views import AuthView
from flask_login import login_user
from flask_appbuilder import expose

# Semi-magical request-local proxy objects
from flask import g, request
from flask import redirect

# ENABLE_PROXY_FIX = True
# SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{os.environ["DB_USER"]}:{os.environ["DB_PASSWORD"]}@{os.environ["DB_HOST"]}/{os.environ["DB_NAME"]}'
# SQLALCHEMY_DATABASE_URI sqlite:////tmp/test.db
LANGUAGES = {'en': {'flag': 'gb', 'name': 'English'}}
SESSION_COOKIE_NAME = 'superset_session'

ADMIN_USERS = ['test@test.com']
SECRET_KEY = 'secret'
UPLOAD_FOLDER = '/tmp/superset-uploads/'
PREVENT_UNSAFE_DB_CONNECTIONS = False

base_role_names = {
    'superset.dataworkspace.test:8000': 'Public',
    'superset-edit.dataworkspace.test:8000': 'Gamma',
    'superset-admin.dataworkspace.test:8000': 'Admin',
}

class DataWorkspaceRemoteUserView(AuthView):
    @expose('/login/')
    def login(self):
        role_name = base_role_names[request.host]
        print('THE ROLE NAME ', role_name, g.user)

        # If user already logged in, redirect to index...
        if g.user is not None and g.user.is_authenticated:
            return redirect(self.appbuilder.get_url_for_index)

        security_manager = self.appbuilder.sm
        username = 'test---' + role_name

        # ... else if user exists but not logged in, log in, and redirect to index
        user = security_manager.find_user(username=username)
        if user is not None:
            login_user(user)
            return redirect(self.appbuilder.get_url_for_index)

        # ... else create user, login, and redirect to index
        app = self.appbuilder.get_app
        is_admin = True
        admin_role = app.config['AUTH_ROLE_ADMIN']
        public_role = app.config['AUTH_ROLE_PUBLIC']

        user = security_manager.add_user(
            username=username,
            first_name='Michal',
            last_name='Test',
            email='test@test.com---' + role_name,
            role=security_manager.find_role(role_name),
        )
        print("Added user", user)
        login_user(user)
        return redirect(self.appbuilder.get_url_for_index)


class DataWorkspaceSecurityManager(SupersetSecurityManager):
    # The Flask AppBuilder Security Manager, from which the Superset Security Manager
    # inherits, uses this if AUTH_TYPE == AUTH_REMOTE_USER
    authremoteuserview = DataWorkspaceRemoteUserView


CUSTOM_SECURITY_MANAGER = DataWorkspaceSecurityManager
AUTH_TYPE = AUTH_REMOTE_USER


def DB_CONNECTION_MUTATOR(uri, params, username, security_manager, source):
    print('---------')
    print(uri)
    print(params)
    print(username)
    print(security_manager)
    print(source)
    # Can this exist??
    print(request)
    return (uri, params)

print("END OF CONFIG!")
