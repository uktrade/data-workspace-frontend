import secrets
import string
import logging
import datetime

from django.conf import settings
from django.core.cache import cache
import gevent
import redis

from arango import ArangoClient
from arango.exceptions import ServerConnectionError, UserCreateError
from dataworkspace.apps.arangodb.models import (
    ApplicationInstanceArangoUsers,
    ArangoUser,
)
from dataworkspace.apps.core.models import Team
from dataworkspace.apps.datasets.models import ArangoDocumentCollection
from dataworkspace.cel import celery_app


logger = logging.getLogger("app")


def new_private_arangodb_credentials(
    dataset_collections,
    datasets_db,
    db_user,
    dw_user,
):
    # ArangoDB database names must start with a letter - '_' removed from start of team.schema_name for database.
    team_dbs = [
        team.schema_name.lstrip("_")
        for team in Team.objects.filter(platform="postgres-and-arango", member=dw_user)
    ]

    # Return no credentials if no access
    if not team_dbs and not dataset_collections:
        return {}

    database_data = settings.ARANGODB
    password_alphabet = string.ascii_letters + string.digits
    db_password = "".join(secrets.choice(password_alphabet) for i in range(64))

    try:
        logger.info("Connecting as root to ArangoDB")
        client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")
        sys_db = client.db(
            "_system", username="root", password=database_data["PASSWORD"], verify=True
        )

        # Create a temporary user in ArangoDB with default permissions
        sys_db.create_user(
            username=db_user,
            password=db_password,
            active=True,
        )
        ArangoUser.objects.create(owner=dw_user, username=db_user)
    except ServerConnectionError:
        logger.info("ArangoDB connection error")
        return {}
    except UserCreateError:
        logger.info("Unable to create user %s in ArangoDB", db_user)
        return {}

    if dataset_collections:
        # Add database level read only permission
        sys_db.update_permission(
            username=db_user,
            permission="ro",
            database=datasets_db,
        )

        # Find existing collections in ArangoDB
        existing_db_collections = client.db(
            datasets_db, username="root", password=database_data["PASSWORD"]
        ).collections()

        # Set default permission to none for all non-system collections
        for existing_collection in existing_db_collections:
            if not existing_collection["system"]:
                sys_db.update_permission(
                    username=db_user,
                    permission="none",
                    database=datasets_db,
                    collection=existing_collection["name"],
                )

        for collection in dataset_collections:
            if not collection["collection"] in [c["name"] for c in existing_db_collections]:
                logger.info(
                    "Collection %s not found in Arango %s database",
                    collection["collection"],
                    datasets_db,
                )
                continue

            logger.info(
                "Setting read permission on %s for collection %s",
                datasets_db,
                collection,
            )
            sys_db.update_permission(
                username=db_user,
                permission="ro",
                database=datasets_db,
                collection=collection["collection"],
            )

    for team_db in team_dbs:
        # Create a team database if it doesnt already exist
        if not sys_db.has_database(team_db):
            logger.info("Creating team database %s in ArangoDB", team_db)
            sys_db.create_database(team_db)

        # Give temporary user credentials read write access to team databases
        logger.info("Adding credentials for database %s in ArangoDB", team_db)
        sys_db.update_permission(
            username=db_user,
            permission="rw",
            database=team_db,
        )

    return {
        "ARANGO_DATABASE": datasets_db,
        "ARANGO_HOST": database_data["HOST"],
        "ARANGO_PORT": database_data["PORT"],
        "ARANGO_USER": db_user,
        "ARANGO_PASSWORD": db_password,
    }


def arango_document_collections_for_user(user):
    req_collections = ArangoDocumentCollection.objects.filter(
        dataset__datasetuserpermission__user=user,
    ).values(
        "reference_number",
        "dataset__id",
        "collection",
    )

    dataset_collections = [
        {
            "dataset_id": x["dataset__id"],
            "collection": x["collection"],
        }
        for x in req_collections
    ]
    return dataset_collections


@celery_app.task()
def delete_unused_arangodb_users():
    try:
        with cache.lock("delete_unused_arangodb_users", blocking_timeout=0, timeout=1800):
            _do_delete_unused_arangodb_users()
    except redis.exceptions.LockNotOwnedError:
        logger.info("delete_unused_arangodb_users: Lock not owned - running on another instance?")
    except redis.exceptions.LockError:
        logger.info(
            "delete_unused_arangodb_users: Unable to grab lock - running on another instance?"
        )


def _do_delete_unused_arangodb_users():
    logger.info("delete_unused_arangodb_users: Start")

    logger.info("delete_unused_arangodb_users: finding temporary database users")
    try:
        database_data = settings.ARANGODB
        client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")
        sys_db = client.db(
            "_system", username="root", password=database_data["PASSWORD"], verify=True
        )
    except ServerConnectionError:
        logger.info("ArangoDB connection error")
        return None

    temporary_usernames = [
        user["username"] for user in sys_db.users() if user["username"].startswith("user_")
    ]

    logger.info("delete_unused_arangodb_users: waiting in case they were just created")
    gevent.sleep(15)

    in_use_usenames = set(
        ApplicationInstanceArangoUsers.objects.filter(
            db_username__in=temporary_usernames,
            application_instance__state__in=["RUNNING", "SPAWNING"],
        ).values_list("db_username", flat=True)
    )

    not_in_use_usernames = [
        usename for usename in temporary_usernames if usename not in in_use_usenames
    ]

    for username in not_in_use_usernames:
        logger.info(
            "delete_unused_arangodb_users: revoking credentials for %s",
            username,
        )
        sys_db.delete_user(username)
        ArangoUser.objects.filter(username=username).update(deleted_date=datetime.datetime.now())
    return None
