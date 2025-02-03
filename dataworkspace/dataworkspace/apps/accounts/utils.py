import logging
from functools import wraps

import requests
from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    authenticate,
    get_user_model,
)
from django.contrib.sessions.backends.base import CreateError
from django.http import HttpResponseForbidden

logger = logging.getLogger("app")


class SSOApiException(Exception):
    pass


def login_required(func):
    @wraps(func)
    def _login_required(request, *args, **kwargs):
        user = authenticate(request)
        if user is None:
            logger.error("Unauthenticated %s", request)
            return HttpResponseForbidden()

        request.user = user
        session = request.session

        # The session cookie is created by the proxy, but the Django session
        # implementation does not support the case where the session has not
        # been created in the cache (just as an empty dict), but the session
        # cookie already exists
        if session.cache_key not in session._cache:
            try:
                session.save(must_create=True)
            except CreateError:
                # Between checking if the key exists and creating the session
                # there could have been a parallel request
                pass

        # We perform a manual "login" for the admin application, since we
        # only decorate the admin login view, and the other admin views
        # require keys set on the session. We don't use Django's default
        # "login" function since it creates a new session cookie to avoid a
        # session fixation attack. Since we're using the same cookie as the
        # proxy, which performs its own session fixation mitigation, this is
        # acceptable
        #
        # Note that for _all_ requests the proxy confirms the session cookie
        # corresponds to an active token with SSO, so it is acceptable
        # to assume that once a request reaches the Django application,
        # the request has been authenticated
        if BACKEND_SESSION_KEY not in session:
            session[BACKEND_SESSION_KEY] = user.backend

        if SESSION_KEY not in session:
            session[SESSION_KEY] = user.id

        if HASH_SESSION_KEY not in session:
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()

        return func(request, *args, **kwargs)

    return _login_required


def add_user_access_profile(user, access_profile_name):
    return _process_user_access_profile(user, access_profile_name, requests.put)


def remove_user_access_profile(user, access_profile_name):
    return _process_user_access_profile(user, access_profile_name, requests.delete)


def _process_user_access_profile(user, access_profile_name, func):
    sso_base_url = settings.AUTHBROKER_URL
    sso_admin_scope_token = settings.SSO_ADMIN_SCOPE_TOKEN

    response = func(
        sso_base_url + f"api/v1/user/permission/{user.profile.sso_id}/",
        data={"access-profile-slug": access_profile_name},
        headers={"Authorization": f"Bearer {sso_admin_scope_token}"},
    )

    try:
        response.raise_for_status()
    except Exception as e:
        logger.exception(e)
        raise SSOApiException from None


def get_user_by_sso_id(sso_id):
    user_model = get_user_model()
    # Attempt to find a user with the given SSO ID as username
    try:
        return user_model.objects.get(username=sso_id)
    except user_model.DoesNotExist:
        # If username doesn't exist fall back to profile sso id.
        return user_model.objects.get(profile__sso_id=sso_id)
