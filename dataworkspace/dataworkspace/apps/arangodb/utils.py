import datetime
import logging
import secrets
import string

import gevent
import redis
from arango import ArangoClient
from arango.exceptions import ServerConnectionError, UserCreateError
from django.conf import settings
from django.core.cache import cache

from dataworkspace.apps.arangodb.models import ApplicationInstanceArangoUsers, ArangoUser
from dataworkspace.apps.core.models import Team
from dataworkspace.cel import celery_app

logger = logging.getLogger("app")


def new_private_arangodb_credentials(
    db_user,
    dw_user,
):

    # ArangoDB database names must start with a letter - '_' removed from start of team.schema_name for database.
    team_dbs = [
        team.schema_name.lstrip("_")
        for team in Team.objects.filter(platform="postgres-and-arango", member=dw_user)
    ]

    database_data = settings.ARANGODB
    if not team_dbs or not database_data:
        return {}

    password_alphabet = string.ascii_letters + string.digits
    db_password = "".join(secrets.choice(password_alphabet) for i in range(64))

    try:
        logger.info("Connecting as root to ArangoDB")
        client = ArangoClient(
            hosts=f"{database_data['PROTOCOL']}://{database_data['HOST']}:{database_data['PORT']}"
        )
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
        logger.exception("ArangoDB connection error")
    except UserCreateError:
        logger.exception("Unable to create user %s in ArangoDB", db_user)

    try:
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
            "ARANGO_HOST": database_data["HOST"],
            "ARANGO_PORT": database_data["PORT"],
            "ARANGO_USER": db_user,
            "ARANGO_PASSWORD": db_password,
        }

    except Exception:  # pylint: disable=broad-except
        logger.exception("Unable to add team database permissions for %s in ArangoDB", db_user)
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

    database_data = settings.ARANGODB
    if not database_data:
        logger.info("delete_unused_arangodb_users: End  ArangoDB connection variables unavailable")
        return None

    logger.info("delete_unused_arangodb_users: finding temporary database users")
    try:
        client = ArangoClient(
            hosts=f"{database_data['PROTOCOL']}://{database_data['HOST']}:{database_data['PORT']}"
        )
        sys_db = client.db(
            "_system", username="root", password=database_data["PASSWORD"], verify=True
        )
    except ServerConnectionError:
        logger.info("delete_unused_arangodb_users: End  ArangoDB connection error")
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
