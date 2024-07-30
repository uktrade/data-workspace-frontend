import secrets
import string
import logging

from django.conf import settings
from django.core.cache import cache
import gevent
import redis

from arango import ArangoClient
from dataworkspace.apps.arangodb.models import (
    ApplicationInstanceArangoUsers,
    ArangoTeam,
)
from dataworkspace.cel import celery_app


logger = logging.getLogger("app")


def new_private_arangodb_credentials(
    db_user,
    user,
):
    password_alphabet = string.ascii_letters + string.digits

    team_dbs = [team.database_name for team in ArangoTeam.objects.filter(member=user)]

    try:
        logger.info("Getting new credentials for temporary user in ArangoDB")

        if team_dbs:

            # Make team databases
            database_data = settings.ARANGODB
            client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")
            sys_db = client.db("_system", username="root", password=database_data["PASSWORD"])

            # Make temporary user
            db_password = "".join(secrets.choice(password_alphabet) for i in range(64))
            if not sys_db.has_user(db_user):
                sys_db.create_user(
                    username=db_user,
                    password=db_password,
                    active=True,
                )

            # Give user read write access to temporary db
            for team_db in team_dbs:

                logger.info("Adding credentials for database %s in ArangoDB", team_db)
                # Create Database if it doesnt already exist
                if not sys_db.has_database(team_db):
                    sys_db.create_database(team_db)

                # Add user permissions
                sys_db.update_permission(
                    username=db_user,
                    permission="rw",
                    database=team_db,
                )

        return {
            "ARANGO_HOST": database_data["HOST"],
            "ARANGO_PORT": database_data["PORT"],
            "ARANGO_USER": db_user,
            "ARANGO_PASSWORD": db_password,
        }

    except Exception:  # pylint: disable=broad-except
        logger.info("Unable to create temporary user in ArangoDB")
        return {}


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
