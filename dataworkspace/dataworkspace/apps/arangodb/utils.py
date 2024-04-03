import datetime
import logging
import os
import secrets
import string
import time
from timeit import default_timer as timer
from typing import Tuple

# from django.conf import settings
from django.contrib.auth import get_user_model
from django.conf import settings

from arango import ArangoClient
from dataworkspace.apps.arangodb.models import (
    ArangoDataset,
    SourceGraphCollection,
)


def new_private_arangodb_credentials(
    db_role_and_schema_suffix,
    source_collections,
    db_user,
    dw_user: get_user_model(),
    valid_for: datetime.timedelta,
):

    password_alphabet = string.ascii_letters + string.digits

    def arango_password():
        return "".join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_memorable_name, collection):
        # Each real-world user is given
        # - a temporary database user
        start_time = time.time()

        # Get ArangoDB database connection variables from environment. 
        database_data = settings.ARANGODB

        # Initialize the ArangoDB client.
        client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")

        # Connect to "_system" database as root user.
        sys_db = client.db('_system', username="root", password=database_data["PASSWORD"])

        # Add new user credentials to Arango per collection for new private creds.
        if not sys_db.has_user(db_user):
            sys_db.create_user(
                username=db_user,
                password=db_password,
                active=True,
            )

        # Update Database Permission
        sys_db.update_permission(
            username=db_user,
            permission='ro',
            database=database_memorable_name,
        )

        # Update Collection Permission
        sys_db.update_permission(
            username=db_user,
            permission='ro',
            database=database_memorable_name,
            collection=collection,
        )

        return {
            "memorable_name": database_memorable_name,
            "db_name": database_data["NAME"],
            "db_host": database_data["HOST"],
            "db_port": database_data["PORT"],
            "db_user": db_user,
            "db_password": db_password,
        }


    # Get Access Permissions by Table
    database_to_collections = {"Datasets": [(collection["dataset"]["id"], collection["dataset"]["name"]) for collection in source_collections]}


    # Get Password
    db_password = arango_password()

    # Get Credentials
    creds = [
        get_new_credentials(db, collection)
        for db, collections in database_to_collections.items()
        for (db_memorable_name, collection) in collections
    ]
    return creds


def source_graph_collections_for_user(user):

    req_collections = SourceGraphCollection.objects.filter(
        graph_dataset__graphdatasetuserpermission__user=user,
    ).values(
        "reference_number",
        "graph_dataset__id",
        "graph_dataset__name",
    )

    source_collections = [
        {
            "dataset": {
                "id": x["graph_dataset__id"],
                # TEMPORARY: Whist name not in source collections
                "name": f"test_{x['reference_number']}",
            },
        }
        for x in req_collections
    ]
    return source_collections


def _arangodb_creds_to_env_vars(arango_credentials=None):
    return dict(
            list(
                {
                    "ARANGO_HOST": arango_credentials[0]["arangodb_host"],
                    "ARANGO_PORT": arango_credentials[0]["arangodb_port"],
                    "ARANGO_DATABASE": arango_credentials[0]["arangodb_name"],
                    "ARANGO_USER": arango_credentials[0]["arangodb_user"],
                    "ARANGO_PASSWORD": arango_credentials[0]["arangodb_password"],
                }.items()
            )
            if arango_credentials
            else []
        )
