# Create your views here.
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from dataworkspace.apps.core.utils import (
    postgres_user,
)
from dataworkspace.apps.arangodb.utils import (
    source_graph_collections_for_user,
    new_private_arangodb_credentials,
    _do_delete_unused_arangodb_users,
)


def TEMPORARY_print_credentials_to_url(request):
    # Get Example User
    user_id = request.user.pk
    user = get_user_model().objects.get(pk=user_id)

    # Get Input to Credentials Generation Function
    (source_collections, db_user) = (
        source_graph_collections_for_user(user),
        postgres_user(user.email),
    )

    credentials = new_private_arangodb_credentials(
        source_collections,
        db_user,
    )

    html = f"<html><body>Credentials are {credentials}.</body></html>"
    return HttpResponse(html)


def TEMPORARY_remove_temp_credentials_to_url(_):
    # Run user removal function
    _do_delete_unused_arangodb_users()

    return HttpResponse("<html><body>Credentials removed.</body></html>")
