import secrets
import string
import logging

from django.conf import settings
from django.core.cache import cache
import gevent
import redis

from arango import ArangoClient
from dataworkspace.apps.arangodb.models import (
    SourceGraphCollection,
    ApplicationInstanceArangoUsers,
)
from dataworkspace.cel import celery_app


logger = logging.getLogger("app")


def new_private_arangodb_credentials(
    source_collections,
    db_user,
    datasets_database="Datasets",
):
    password_alphabet = string.ascii_letters + string.digits

    def set_new_credentials(collection):
        # Each real-world user is given
        # - a temporary database user

        try:
            logger.info(
                "Setting read permission on %s for collection %s",
                datasets_database,
                collection,
            )

            # Update Collection Permission
            sys_db.update_permission(
                username=db_user,
                permission="ro",
                database=datasets_database,
                collection=collection["collection"],
            )

        except Exception:  # pylint: disable=broad-except
            logger.info(
                "Unable to set read permission on %s for collection %s",
                datasets_database,
                collection["collection"],
            )

    if source_collections:
        try:
            logger.info("Getting new credentials for temporary user in ArangoDB")

            # Get ArangoDB database connection variables from environment.
            database_data = settings.ARANGODB

            # Initialize the ArangoDB client.
            client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")

            # Connect to "_system" database as root user.
            sys_db = client.db("_system", username="root", password=database_data["PASSWORD"])

            # Get temporary user password
            db_password = "".join(secrets.choice(password_alphabet) for i in range(64))

            # Add new user credentials to Arango per collection for new private creds.
            if not sys_db.has_user(db_user):
                sys_db.create_user(
                    username=db_user,
                    password=db_password,
                    active=True,
                )

            # Create a new database named database_memorable_name if it does not exist.
            # Move to arango container start up.
            if not sys_db.has_database(datasets_database):
                sys_db.create_database(datasets_database)

            # Find existing collections in ArangoDB
            datasets_db = client.db(
                datasets_database, username="root", password=database_data["PASSWORD"]
            )
            existing_db_collections = datasets_db.collections()

            logger.info(
                "Found %d existing collections in the %s graph db",
                len(existing_db_collections),
                datasets_database,
            )
        except Exception:  # pylint: disable=broad-except
            logger.info("Unable to create temporary user in ArangoDB")
            return {}

        # Set read access to permitted and existing collections
        for collection in source_collections:
            set_new_credentials(collection)

        return {
            "ARANGO_DATABASE": datasets_database,
            "ARANGO_HOST": database_data["HOST"],
            "ARANGO_PORT": database_data["PORT"],
            "ARANGO_USER": db_user,
            "ARANGO_PASSWORD": db_password,
        }

    else:
        return {}


def source_graph_collections_for_user(user):
    req_collections = SourceGraphCollection.objects.filter(
        dataset__datasetuserpermission__user=user,
    ).values(
        "reference_number",
        "dataset__id",
        "collection",
    )

    source_collections = [
        {
            "dataset_id": x["dataset__id"],
            "collection": x["collection"],
        }
        for x in req_collections
    ]
    return source_collections


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

    # Connect to ArangoDB as root user and return all temporary user credentials
    database_data = settings.ARANGODB

    # Initialize the ArangoDB client.
    client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")

    # Connect to "_system" database as root user.
    sys_db = client.db("_system", username="root", password=database_data["PASSWORD"])

    logger.info("delete_unused_arangodb_users: finding temporary database users")
    # Returns all usernames for temporary users
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
