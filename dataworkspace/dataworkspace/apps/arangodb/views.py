# Create your views here.
from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.conf import settings
import datetime

from dataworkspace.apps.core.utils import (
    db_role_schema_suffix_for_user,
    postgres_user,
)
from dataworkspace.apps.arangodb.utils import (
    source_graph_collections_for_user,
    new_private_arangodb_credentials,
    _do_delete_unused_arangodb_users,
)
from dataworkspace.apps.arangodb.models import SourceGraphCollection, ApplicationInstanceArangoUsers



def TEMPORARY_print_credentials_to_url(request):

    # Get Example User
    user_id = request.user.pk
    user = get_user_model().objects.get(pk=user_id)

    # Get Input to Credentials Generation Function
    (source_collections, db_role_schema_suffix, db_user) = (
        source_graph_collections_for_user(user),
        db_role_schema_suffix_for_user(user),
        postgres_user(user.email),
    )

    credentials = new_private_arangodb_credentials(
        db_role_schema_suffix,
        source_collections,
        db_user,
        # user if application_instance.application_template.application_type == "TOOL" else None,
        user,
        valid_for=datetime.timedelta(days=31),
    )

    html = "<html><body>Credentials are %s.</body></html>" % credentials
    return HttpResponse(html)


def TEMPORARY_remove_temp_credentials_to_url(request):

    # Get Example User
    user_id = request.user.pk
    user = get_user_model().objects.get(pk=user_id)

    # Run user removal function
    _do_delete_unused_arangodb_users()

    html = "<html><body>Credentials removed %s.</body></html>"
    return HttpResponse(html)



