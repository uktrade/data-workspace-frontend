import csv
import datetime
import json
import logging
import os
import re
import urllib.parse
from collections import defaultdict
from typing import Dict, List

import boto3
import botocore
import waffle
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connections
from django.db.models import Q
import gevent
from psycopg2 import connect, sql
import requests
from pytz import utc
from smart_open import open as smart_open

import redis

from dataworkspace.apps.accounts.models import Profile
from dataworkspace.apps.accounts.utils import get_user_by_sso_id
from dataworkspace.apps.applications.spawner import (
    get_spawner,
    stop,
    _fargate_task_describe,
    _fargate_task_stop,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationInstanceDbUsers,
    ApplicationTemplate,
)
from dataworkspace.apps.core.errors import (
    DatasetPermissionDenied,
    ManageVisualisationsPermissionDeniedError,
    ToolInvalidUserError,
    ToolPermissionDeniedError,
)
from dataworkspace.apps.core.models import Database, DatabaseUser
from dataworkspace.apps.core.utils import (
    GLOBAL_LOCK_ID,
    close_all_connections_if_not_in_atomic_block,
    create_tools_access_iam_role_task,
    database_dsn,
    stable_identification_suffix,
    source_tables_for_app,
    source_tables_for_user,
    transaction_and_lock,
    new_private_database_credentials,
    postgres_user,
    has_tools_cert_expired,
    is_tools_cert_renewal_due,
)
from dataworkspace.apps.applications.gitlab import gitlab_has_developer_access
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.datasets.models import (
    ToolQueryAuditLog,
    VisualisationCatalogueItem,
)
from dataworkspace.cel import celery_app
from dataworkspace.datasets_db import extract_queried_tables_from_sql_query
from dataworkspace.apps.core.boto3_client import get_s3_resource, get_sts_client
from dataworkspace.notify import EmailSendFailureException, send_email


logger = logging.getLogger("app")


class MetricsException(Exception):
    pass


class ExpectedMetricsException(MetricsException):
    pass


class UnexpectedMetricsException(MetricsException):
    pass


class HawkException(Exception):
    pass


def is_8_char_hex(val):
    try:
        int(val, 16)
    except ValueError:
        return False
    else:
        return len(val) == 8


def application_template_tag_user_commit_from_host(public_host):
    # This does make it impossible for a visualisation to have the host of
    # the form <tool-name>-<user-id>, but I suspect is very unlikely

    # The value after the rightmost '--', if it's there, is the commit id
    possible_host_basename, _, host_basename_or_commit_id = public_host.rpartition("--")
    if possible_host_basename and is_8_char_hex(host_basename_or_commit_id):
        host_basename = possible_host_basename
        commit_id = host_basename_or_commit_id
    else:
        host_basename = public_host
        commit_id = None

    # The value after the rightmost '-', if it's there, is the user id
    possible_host_basename, _, host_basename_or_user = host_basename.rpartition("-")
    if possible_host_basename and is_8_char_hex(host_basename_or_user):
        host_basename = possible_host_basename
        user = host_basename_or_user
    else:
        user = None

    matching_tools = (
        list(
            ApplicationTemplate.objects.filter(
                application_type="TOOL", host_basename=host_basename
            )
        )
        if user
        else []
    )

    matching_visualisations = (
        list(
            ApplicationTemplate.objects.filter(
                application_type="VISUALISATION", host_basename=host_basename
            )
        )
        if not user
        else []
    )

    matching = matching_tools + matching_visualisations

    # Visualisations are all in the same docker repo with different tags,
    # while tools are each in their own repo
    tag = public_host if matching_visualisations else None

    if not matching:
        raise ApplicationTemplate.DoesNotExist()
    if len(matching) > 1:
        raise Exception("Too many ApplicatinTemplate matching host")

    return (matching[0], tag, user, commit_id)


def application_options(application_template):
    common_spawner_options = settings.APPLICATION_SPAWNER_OPTIONS.get(
        application_template.spawner, {}
    ).get(application_template.application_type, {})

    return {
        **common_spawner_options,
        **json.loads(application_template.spawner_options),
    }


def api_application_dict(application_instance, ignore_spawner_state=False):
    if ignore_spawner_state:
        api_state = application_instance.state
    else:
        spawner_state = get_spawner(application_instance.application_template.spawner).state(
            application_instance.spawner_application_template_options,
            application_instance.created_date.replace(tzinfo=None),
            application_instance.spawner_application_instance_id,
            application_instance.public_host,
        )

        # Only pass through the database state if the spawner is running,
        # Otherwise, we are in an error condition, and so return the spawner
        # state, so the client (i.e. the proxy) knows to take action
        api_state = application_instance.state if spawner_state == "RUNNING" else spawner_state

    sso_id_hex_short = stable_identification_suffix(
        str(application_instance.owner.profile.sso_id), short=True
    )

    return {
        "id": application_instance.id,
        "proxy_url": application_instance.proxy_url,
        "state": api_state,
        "user": sso_id_hex_short,
        "wrap": application_instance.application_template.wrap,
        # Used by metrics to label the application
        "name": application_instance.application_template.nice_name,
    }


def get_api_visible_application_instance_by_public_host(public_host):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.get(
        public_host=public_host, state__in=["RUNNING", "SPAWNING"]
    )


def application_api_is_allowed(request, public_host):
    try:
        (
            application_template,
            _,
            host_user,
            commit_id,
        ) = application_template_tag_user_commit_from_host(public_host)
    except ApplicationTemplate.DoesNotExist:
        return False

    visualisation_catalogue_item = None
    if application_template.application_type == "VISUALISATION":
        visualisation_catalogue_item = VisualisationCatalogueItem.objects.get(
            visualisation_template=application_template
        )

    request_sso_id_hex_short = stable_identification_suffix(
        str(request.user.profile.sso_id), short=True
    )
    is_preview = commit_id is not None

    def is_tool_and_correct_user_and_allowed_to_start():
        if application_template.application_type != "TOOL":
            return False
        if host_user != request_sso_id_hex_short:
            raise ToolInvalidUserError()
        if not request.user.has_perm("applications.start_all_applications"):
            raise ToolPermissionDeniedError()
        return True

    def is_published_visualisation_and_requires_authentication():
        return (
            not is_preview
            and application_template.visible is True
            and visualisation_catalogue_item
            and visualisation_catalogue_item.user_access_type
            in (UserAccessType.REQUIRES_AUTHENTICATION, UserAccessType.OPEN)
        )

    def is_published_visualisation_and_requires_authorisation_and_has_authorisation():
        user_email_domain = request.user.email.split("@")[1]

        vis_requires_auth = (
            not is_preview
            and application_template.visible is True
            and visualisation_catalogue_item
            and visualisation_catalogue_item.user_access_type
            == UserAccessType.REQUIRES_AUTHORIZATION
        )
        if (
            vis_requires_auth
            and not request.user.visualisationuserpermission_set.filter(
                visualisation=visualisation_catalogue_item
            ).exists()
            and user_email_domain not in visualisation_catalogue_item.authorized_email_domains
        ):
            raise DatasetPermissionDenied(visualisation_catalogue_item)
        return vis_requires_auth

    def is_visualisation_preview_and_has_gitlab_developer_and_has_dataset_access():
        is_vis_preview = is_preview and visualisation_catalogue_item
        if is_vis_preview and not gitlab_has_developer_access(
            request.user, application_template.gitlab_project_id
        ):
            raise ManageVisualisationsPermissionDeniedError()

        user_source_tables = source_tables_for_user(request.user)
        app_source_tables = source_tables_for_app(application_template)

        user_authorised_datasets = set(
            (source_table["dataset"]["id"] for source_table in user_source_tables)
        )
        app_authorised_datasets = set(
            (source_table["dataset"]["id"] for source_table in app_source_tables)
        )
        if app_authorised_datasets - user_authorised_datasets:
            raise ManageVisualisationsPermissionDeniedError()

        return is_vis_preview

    return (
        is_tool_and_correct_user_and_allowed_to_start()
        or is_published_visualisation_and_requires_authentication()
        or is_published_visualisation_and_requires_authorisation_and_has_authorisation()
        or is_visualisation_preview_and_has_gitlab_developer_and_has_dataset_access()
    )


def stop_spawner_and_application(application_instance):
    stop.delay(application_instance.spawner, application_instance.id)
    set_application_stopped(application_instance)


def set_application_stopped(application_instance):
    application_instance.state = "STOPPED"
    application_instance.single_running_or_spawning_integrity = str(application_instance.id)
    application_instance.save(update_fields=["state", "single_running_or_spawning_integrity"])


def application_instance_max_cpu(application_instance):
    # If we don't have the proxy url yet, we can't have any metrics yet.
    # This is expected and should not be shown as an error
    if application_instance.proxy_url is None:
        raise ExpectedMetricsException("Unknown")

    hostname = urllib.parse.urlsplit(application_instance.proxy_url).hostname

    # If the tool failed to start we then hostname can be None
    if hostname is None:
        raise ExpectedMetricsException("Unknown")

    instance = hostname + ":8889"
    url = f"https://{settings.PROMETHEUS_DOMAIN}/api/v1/query"
    params = {
        "query": f'increase(precpu_stats__cpu_usage__total_usage{{instance="{instance}"}}[30s])[2h:30s]'
    }
    try:
        logger.info("kill_idle_fargate: finding CPU usage for %s", instance)
        response = requests.get(url, params)
    except requests.RequestException:
        # pylint: disable=raise-missing-from
        raise UnexpectedMetricsException("Error connecting to metrics server")

    response_dict = response.json()
    if response_dict["status"] != "success":
        raise UnexpectedMetricsException(
            f'Metrics server return value is {response_dict["status"]}'
        )

    try:
        values = response_dict["data"]["result"][0]["values"]
    except (IndexError, KeyError):
        # The server not having metrics yet should not be reported as an error
        # pylint: disable=raise-missing-from
        raise ExpectedMetricsException("Unknown")

    max_cpu = 0.0
    ts_at_max = 0
    for ts, cpu in values:
        cpu_float = float(cpu) / (1_000_000_000 * 30) * 100
        if cpu_float >= max_cpu:
            max_cpu = cpu_float
            ts_at_max = ts

    return max_cpu, ts_at_max


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def kill_idle_fargate():
    try:
        with cache.lock("do_kill_idle_fargate", blocking_timeout=0, timeout=3600):
            do_kill_idle_fargate()
    except redis.exceptions.LockError as e:
        logger.warning("Failed to acquire lock for do_kill_idle_fargate: %s", e)


def do_kill_idle_fargate():
    logger.info("kill_idle_fargate: Start")

    two_hours_ago = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=-2)
    instances = ApplicationInstance.objects.filter(
        spawner="FARGATE",
        state__in=["RUNNING", "SPAWNING"],
        created_date__lt=two_hours_ago,
    )

    for instance in instances:
        if instance.state == "SPAWNING":
            stop_spawner_and_application(instance)
            continue

        logger.info("kill_idle_fargate: Attempting to find CPU usage of %s", instance)
        try:
            max_cpu, _ = application_instance_max_cpu(instance)
        except ExpectedMetricsException:
            logger.info("kill_idle_fargate: Unable to find CPU usage for %s", instance)
            continue
        except Exception:  # pylint: disable=broad-except
            logger.exception("kill_idle_fargate: Unable to find CPU usage for %s", instance)
            continue

        logger.info("kill_idle_fargate: CPU usage for %s is %s", instance, max_cpu)

        if max_cpu >= 1.0:
            continue

        try:
            stop_spawner_and_application(instance)
        except Exception:  # pylint: disable=broad-except
            logger.exception("kill_idle_fargate: Unable to stop %s", instance)

        logger.info("kill_idle_fargate: Stopped application %s", instance)

    logger.info("kill_idle_fargate: End")


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def populate_created_stopped_fargate():
    try:
        with cache.lock("populate_created_stopped_fargate", blocking_timeout=0, timeout=3600):
            do_populate_created_stopped_fargate()
    except redis.exceptions.LockError as e:
        logger.warning("Failed to acquire lock for populate_created_stopped_fargate: %s", e)


def do_populate_created_stopped_fargate():
    logger.info("populate_created_stopped_fargate: Start")

    # This is used to populate spawner_created_at and spawner_stopped_at for
    # Fargate containers in two case:
    #
    # - For any that failed to populate spawner_created_at and
    #   spawner_stopped_at. This is possible since they are populated
    #   asynchronously, and although they retry on failure, it's not perfect
    #   if the Django instance went down at that moment
    #
    # - For those that existed before spawner_created_at, spawner_stopped_at
    #   were added. Unfortunately it appears that tasks are only stored for
    #   about 15 hours after they stop
    #   https://github.com/aws/amazon-ecs-agent/issues/368 so this is only
    #   of limited use
    #
    # We go back ~2 days of applications out of a bit of hope that more tasks
    # are stored. We also do an hour at a time to leverage the index on
    # created_date and just in case this is ever used for high numbers of
    # applications. We deliberately don't add an indexes for this case since
    # it's deemed not worth slowing inserts or using more disk space for this
    # non performance critical background task

    # Ensure we don't have a moving target of "now" during processing
    now = datetime.datetime.now(datetime.timezone.utc)

    for hours in range(0, 48):
        start_of_range = now + datetime.timedelta(hours=-hours - 1)
        end_of_range = now + datetime.timedelta(hours=-hours)
        instances = ApplicationInstance.objects.filter(
            Q(
                spawner="FARGATE",
                created_date__gte=start_of_range,
                created_date__lt=end_of_range,
            )
            & (Q(spawner_created_at__isnull=True) | Q(spawner_stopped_at__isnull=True))
        ).order_by("-created_date")

        for instance in instances:
            logger.info("populate_created_stopped_fargate checking: %s", instance)

            try:
                options = json.loads(instance.spawner_application_template_options)
                cluster_name = options["CLUSTER_NAME"]
                task_arn = json.loads(instance.spawner_application_instance_id)["task_arn"]
            except (ValueError, KeyError):
                continue

            if not task_arn:
                continue

            # To not bombard the ECS API
            gevent.sleep(0.1)
            try:
                task = _fargate_task_describe(cluster_name, task_arn)
            except Exception:  # pylint: disable=broad-except
                logger.exception("populate_created_stopped_fargate %s", instance)
                gevent.sleep(10)
                continue

            if not task:
                logger.info(
                    "populate_created_stopped_fargate no task found %s %s",
                    instance,
                    task_arn,
                )
                continue

            update_fields = []
            if "createdAt" in task and instance.spawner_created_at is None:
                instance.spawner_created_at = task["createdAt"]
                update_fields.append("spawner_created_at")

            if "stoppedAt" in task and instance.spawner_stopped_at is None:
                instance.spawner_stopped_at = task["stoppedAt"]
                update_fields.append("spawner_stopped_at")

            if update_fields:
                logger.info(
                    "populate_created_stopped_fargate saving: %s %s",
                    instance,
                    update_fields,
                )
                instance.save(update_fields=update_fields)

    logger.info("populate_created_stopped_fargate: End")


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def delete_unused_datasets_users():
    try:
        with cache.lock("delete_unused_datasets_users", blocking_timeout=0, timeout=1800):
            _do_delete_unused_datasets_users()
    except redis.exceptions.LockNotOwnedError:
        logger.info("delete_unused_datasets_users: Lock not owned - running on another instance?")
    except redis.exceptions.LockError:
        logger.info(
            "delete_unused_datasets_users: Unable to grab lock - running on another instance?"
        )


def _do_delete_unused_datasets_users():
    logger.info("delete_unused_datasets_users: Start")

    for memorable_name, database_data in settings.DATABASES_DATA.items():
        database_obj = Database.objects.get(memorable_name=memorable_name)
        database_name = database_data["NAME"]

        with connect(database_dsn(database_data)) as conn, conn.cursor() as cur:
            logger.info("delete_unused_datasets_users: finding database users")
            cur.execute(
                """
                SELECT usename FROM pg_catalog.pg_user
                WHERE
                (
                    valuntil != 'infinity'
                    AND usename LIKE 'user_%'
                    AND usename NOT LIKE '%_qs'
                    AND usename NOT LIKE '%_quicksight'
                    AND usename NOT LIKE '%_explorer'
                    AND usename NOT LIKE '%_superset'
                )
                OR
                (
                    valuntil != 'infinity'
                    AND valuntil < now()
                    AND usename LIKE 'user_%' AND
                    (
                        usename LIKE '%_qs'
                        OR usename LIKE '%_explorer'
                        OR usename LIKE '%_superset'
                    )
                )
                ORDER BY usename;
                """
            )
            usenames = [result[0] for result in cur.fetchall()]

        logger.info("delete_unused_datasets_users: waiting in case they were just created")
        gevent.sleep(15)

        # We want to be able to delete db users created, but then _not_ associated with an
        # running application, such as those from a STOPPED application, but also from those
        # that were created but then the server went down before the application was created.
        in_use_usenames = set(
            ApplicationInstanceDbUsers.objects.filter(
                db=database_obj,
                db_username__in=usenames,
                application_instance__state__in=["RUNNING", "SPAWNING"],
            ).values_list("db_username", flat=True)
        )
        not_in_use_usernames = [usename for usename in usenames if usename not in in_use_usenames]
        logger.info(
            "delete_unused_datasets_users: not_in_use_usernames %s",
            not_in_use_usernames,
        )

        # Persistent db roles are needed in order to reassign objects owned by the temporary user role
        # before it gets dropped.
        db_persistent_roles = {
            db_user[0]: db_user[1]
            for db_user in set(
                ApplicationInstanceDbUsers.objects.filter(
                    db=database_obj,
                    db_username__in=not_in_use_usernames,
                ).values_list("db_username", "db_persistent_role")
            )
        }
        logger.info(
            "delete_unused_datasets_users: db_persistent_roles %s",
            db_persistent_roles,
        )

        # Multiple concurrent GRANT or REVOKE on the same object can result in
        # "tuple concurrently updated" errors
        with connect(
            database_dsn(database_data)
        ) as conn, conn.cursor() as cur, transaction_and_lock(cur, GLOBAL_LOCK_ID):
            for usename in not_in_use_usernames:
                try:
                    logger.info(
                        "delete_unused_datasets_users: revoking credentials for %s",
                        usename,
                    )

                    cur.execute(
                        sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {};").format(
                            sql.Identifier(database_name),
                            sql.Identifier(usename),
                        )
                    )

                    cur.execute(
                        sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {};").format(
                            sql.Identifier(database_name),
                            sql.Identifier(usename),
                        )
                    )

                    logger.info(
                        "delete_unused_datasets_users: dropping user %s",
                        usename,
                    )

                    # Revoke privileges so that the DROP USER command succeeds
                    if usename in db_persistent_roles:
                        db_persistent_role = db_persistent_roles[usename]
                        # This reassigns the ownership of all the database objects owned by
                        # the temporary role, however it does not handle privileges so these
                        # need to be revoked in the next command.
                        #
                        # REASSIGN OWNED requires privileges on both the source role(s) and
                        # the target role so these are granted first.
                        cur.execute(
                            sql.SQL("GRANT {} TO {};").format(
                                sql.Identifier(usename),
                                sql.Identifier(database_data["USER"]),
                            )
                        )
                        cur.execute(
                            sql.SQL("GRANT {} TO {};").format(
                                sql.Identifier(db_persistent_role),
                                sql.Identifier(database_data["USER"]),
                            )
                        )

                        # The REASSIGN OWNED BY means any objects like tables that were
                        # owned by the temporary user get transferred to the permanent user
                        cur.execute(
                            sql.SQL("REASSIGN OWNED BY {} TO {};").format(
                                sql.Identifier(usename),
                                sql.Identifier(db_persistent_role),
                            )
                        )
                        # ... so the only effect of DROP OWNED BY is to REVOKE any
                        # remaining permissions by the temporary user, so it can then get
                        # deleted below
                        cur.execute(sql.SQL("DROP OWNED BY {};").format(sql.Identifier(usename)))

                        # ... and then cleanup the roles on the master user (since there are
                        # performance implications for the master user having a lot of roles,
                        # specifically it can cause slowness on connect)
                        cur.execute(
                            sql.SQL("REVOKE {} FROM {};").format(
                                sql.Identifier(usename),
                                sql.Identifier(database_data["USER"]),
                            )
                        )
                        cur.execute(
                            sql.SQL("REVOKE {} FROM {};").format(
                                sql.Identifier(db_persistent_role),
                                sql.Identifier(database_data["USER"]),
                            )
                        )

                    cur.execute(sql.SQL("DROP USER {};").format(sql.Identifier(usename)))
                except Exception:  # pylint: disable=broad-except
                    logger.exception(
                        "delete_unused_datasets_users: Failed deleting %s",
                        usename,
                    )
                else:
                    DatabaseUser.objects.filter(username=usename).update(
                        deleted_date=datetime.datetime.now()
                    )
                    logger.info(
                        "delete_unused_datasets_users: revoked credentials for and dropped %s",
                        usename,
                    )

    logger.info("delete_unused_datasets_users: End")


def get_quicksight_dashboard_name_url(dashboard_id, user):
    user_region = settings.QUICKSIGHT_USER_REGION
    embed_role_arn = settings.QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN
    embed_role_name = embed_role_arn.rsplit("/", 1)[1]
    sso_id = str(user.profile.sso_id)

    sts = get_sts_client()
    account_id = sts.get_caller_identity().get("Account")

    role_credentials = sts.assume_role(RoleArn=embed_role_arn, RoleSessionName=sso_id)[
        "Credentials"
    ]

    session = boto3.Session(
        aws_access_key_id=role_credentials["AccessKeyId"],
        aws_secret_access_key=role_credentials["SecretAccessKey"],
        aws_session_token=role_credentials["SessionToken"],
    )

    # QuickSight manages users in a separate region to our data/dashboards.
    qs_user_client = session.client("quicksight", region_name=user_region)
    qs_dashboard_client = session.client("quicksight")

    try:
        qs_user_client.register_user(
            AwsAccountId=account_id,
            Namespace=settings.QUICKSIGHT_NAMESPACE,
            IdentityType="IAM",
            IamArn=embed_role_arn,
            UserRole="READER",
            SessionName=sso_id,
            Email=sso_id,
        )
    except qs_user_client.exceptions.ResourceExistsException:
        pass

    attempts = 5
    while attempts > 0:
        attempts -= 1
        try:
            qs_user_client.create_group_membership(
                AwsAccountId=account_id,
                Namespace=settings.QUICKSIGHT_NAMESPACE,
                GroupName=settings.QUICKSIGHT_DASHBOARD_GROUP,
                MemberName=f"{embed_role_name}/{sso_id}",
            )
            break

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                if attempts > 0:
                    gevent.sleep(5 - attempts)
                else:
                    raise e
            else:
                raise e

    dashboard_name = qs_dashboard_client.describe_dashboard(
        AwsAccountId=account_id, DashboardId=dashboard_id, AliasName="$PUBLISHED"
    )["Dashboard"]["Name"]
    dashboard_url = qs_dashboard_client.get_dashboard_embed_url(
        AwsAccountId=account_id,
        DashboardId=dashboard_id,
        IdentityType="QUICKSIGHT",
        UserArn=f"arn:aws:quicksight:{user_region}:{account_id}:user/"
        + f"{settings.QUICKSIGHT_NAMESPACE}/{embed_role_name}/{sso_id}",
    )["EmbedUrl"]

    return dashboard_name, dashboard_url


def get_data_source_id(db_name, quicksight_user_arn):
    return (
        "data-workspace-"
        + settings.ENVIRONMENT.lower()
        + "-"
        + db_name
        + "-"
        + stable_identification_suffix(quicksight_user_arn, short=True)
    )


def create_update_delete_quicksight_user_data_sources(
    data_client, account_id, quicksight_user, creds
):
    env = settings.ENVIRONMENT.lower()
    qs_datasource_perms = [
        "quicksight:DescribeDataSource",
        "quicksight:DescribeDataSourcePermissions",
        "quicksight:PassDataSource",
    ]

    authorized_data_source_ids = set()

    # Create/update any data sources the user has access to
    for cred in creds:
        db_name = cred["memorable_name"]
        data_source_id = get_data_source_id(db_name, quicksight_user["Arn"])
        data_source_name = f"Data Workspace - {db_name}"
        if env != "production":
            data_source_name = f"{env.upper()} - {data_source_name}"

        create_and_update_params = dict(
            AwsAccountId=account_id,
            DataSourceId=data_source_id,
            Name=data_source_name,
            DataSourceParameters={
                "AuroraPostgreSqlParameters": {
                    "Host": cred["db_host"],
                    "Port": int(cred["db_port"]),
                    "Database": cred["db_name"],
                }
            },
            Credentials={
                "CredentialPair": {
                    "Username": cred["db_user"],
                    "Password": cred["db_password"],
                }
            },
            VpcConnectionProperties={"VpcConnectionArn": settings.QUICKSIGHT_VPC_ARN},
        )

        logger.info("-> Creating data source: %s", data_source_id)

        try:
            data_client.create_data_source(
                **create_and_update_params,
                Type="AURORA_POSTGRESQL",
                Permissions=[
                    {
                        "Principal": quicksight_user["Arn"],
                        "Actions": qs_datasource_perms,
                    }
                ],
            )
            logger.info("-> Created: %s", data_source_id)

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                logger.info("-> Data source already exists: %s. Updating ...", data_source_id)
                data_client.update_data_source(**create_and_update_params)
                logger.info("-> Updated data source: %s", data_source_id)

            else:
                raise e

        authorized_data_source_ids.add(data_source_id)

    # Delete any data sources the user no longer has access to
    all_data_source_ids = {
        get_data_source_id(db_name, quicksight_user["Arn"])
        for db_name in settings.DATABASES_DATA.keys()
    }
    unauthorized_data_source_ids = all_data_source_ids - {
        get_data_source_id(cred["memorable_name"], quicksight_user["Arn"]) for cred in creds
    }
    logger.info(all_data_source_ids)
    logger.info(unauthorized_data_source_ids)
    for unauthorized_data_source_id in unauthorized_data_source_ids:
        logger.info("-> Deleting data source: %s", unauthorized_data_source_id)
        try:
            data_client.delete_data_source(
                AwsAccountId=account_id, DataSourceId=unauthorized_data_source_id
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pass

            else:
                raise e


def sync_quicksight_users(data_client, user_client, account_id, quicksight_user_list):
    for quicksight_user in quicksight_user_list:
        user_arn = quicksight_user["Arn"]
        user_role = quicksight_user["Role"]
        user_username = quicksight_user["UserName"]
        sso_id = quicksight_user["UserName"].split("/")[-1]

        # Update the quicksight user's email address to match data workspace
        try:
            user_email = get_user_model().objects.get(username=sso_id).email
        except get_user_model().DoesNotExist:
            user_email = quicksight_user["Email"].lower()

        if user_role not in {"AUTHOR", "ADMIN"}:
            logger.info("Skipping %s with role %s.", user_email, user_role)
            continue

        try:
            # Lightly enforce that only instance can edit permissions for a user at a time.
            with cache.lock(
                f"sync-quicksight-permissions-{user_arn}",
                blocking_timeout=60,
                timeout=360,
            ):
                try:
                    if user_role == "ADMIN":
                        user_client.update_user(
                            AwsAccountId=account_id,
                            Namespace=settings.QUICKSIGHT_NAMESPACE,
                            Role=user_role,
                            UnapplyCustomPermissions=True,
                            UserName=user_username,
                            Email=user_email,
                        )
                    else:
                        user_client.update_user(
                            AwsAccountId=account_id,
                            Namespace=settings.QUICKSIGHT_NAMESPACE,
                            Role=user_role,
                            CustomPermissionsName=settings.QUICKSIGHT_AUTHOR_CUSTOM_PERMISSIONS,
                            UserName=user_username,
                            Email=user_email,
                        )

                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        continue  # Can be raised if the user has been deactivated/"deleted"

                    raise e

                try:
                    dw_user = get_user_by_sso_id(sso_id)
                except ValidationError:
                    dw_user = None

                if not dw_user:
                    logger.error(
                        "Skipping %s - cannot match with Data Workspace user.",
                        user_email,
                    )
                    continue

                # We technically ignore the case for where a single email has multiple matches on DW, but I'm not
                # sure this is a case that can happen - and if it can, we don't care while prototyping.
                logger.info("Syncing QuickSight resources for %s", dw_user)

                source_tables = source_tables_for_user(dw_user)
                db_role_schema_suffix = stable_identification_suffix(str(sso_id), short=True)

                # This creates a DB user for each of our datasets DBs. These users are intended to be long-lived,
                # so they might already exist. If this is the case, we still generate a new password, as at the moment
                # these user accounts only last for 31 days by default - so we need to update the password to keep them
                # from expiring.
                creds = new_private_database_credentials(
                    db_role_schema_suffix,
                    source_tables,
                    postgres_user(user_email, suffix="qs"),
                    dw_user,
                    valid_for=datetime.timedelta(
                        days=7
                    ),  # We refresh these creds every night, so they don't need to last long at all.
                )

                create_update_delete_quicksight_user_data_sources(
                    data_client, account_id, quicksight_user, creds
                )

        # We want to sync as many users as possible even if some failed
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unable to sync permissions for %s", quicksight_user["Arn"])


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def sync_quicksight_permissions(user_sso_ids_to_update=tuple()):
    logger.info(
        "sync_quicksight_user_datasources(%s) started",
        user_sso_ids_to_update,
    )

    # QuickSight manages users in a single specific regions
    user_client = boto3.client(
        "quicksight",
        region_name=settings.QUICKSIGHT_USER_REGION,
        config=Config(retries={"mode": "standard", "max_attempts": 10}),
    )
    # Data sources can be in other regions - so here we use the Data Workspace default from its env vars.
    data_client = boto3.client("quicksight")

    account_id = boto3.client("sts").get_caller_identity().get("Account")
    username_suffix = (
        "" if settings.QUICKSIGHT_NAMESPACE == "default" else ("_" + settings.QUICKSIGHT_NAMESPACE)
    )
    quicksight_user_list: List[Dict[str, str]]
    if len(user_sso_ids_to_update) > 0:
        quicksight_user_list = []

        for user_sso_id in user_sso_ids_to_update:
            try:
                quicksight_user_list.append(
                    user_client.describe_user(
                        AwsAccountId=account_id,
                        Namespace=settings.QUICKSIGHT_NAMESPACE,
                        # \/ This is the format of the user name created by DIT SSO \/
                        UserName=f"quicksight_federation{username_suffix}/{user_sso_id}",
                    )["User"]
                )
            except botocore.exceptions.ClientError as e:
                logger.info(
                    "describe_user failed with %s for user %s",
                    e.response["Error"]["Code"],
                    user_sso_id,
                )

        sync_quicksight_users(
            data_client=data_client,
            user_client=user_client,
            account_id=account_id,
            quicksight_user_list=quicksight_user_list,
        )

    else:
        quicksight_user_list: List[Dict[str, str]] = []
        next_token = None
        while True:
            list_user_args = dict(AwsAccountId=account_id, Namespace=settings.QUICKSIGHT_NAMESPACE)
            if next_token:
                list_user_args["NextToken"] = next_token

            try:
                list_users_response = user_client.list_users(**list_user_args)
            except botocore.exceptions.ClientError as e:
                # There is a bug in the Quicksight API where it throws a ResourceNotFound after
                # a certain number of records. There is not much we can do at the moment other
                # than catch it and process what we have
                if (
                    e.response["Error"]["Code"] == "ResourceNotFoundException"
                    and len(quicksight_user_list) > 0
                ):
                    logger.error(
                        "Failed to fetch all Quicksight users due to a known "
                        "issue with the Quicksight API"
                    )
                    break
                raise e
            quicksight_user_list.extend(list_users_response["UserList"])
            next_token = list_users_response.get("NextToken")

            if not next_token:
                break

        logger.info(
            "starting sync_quicksight_permissions for %s number of users",
            len(quicksight_user_list),
        )
        sync_quicksight_users(
            data_client=data_client,
            user_client=user_client,
            account_id=account_id,
            quicksight_user_list=quicksight_user_list,
        )

    logger.info(
        "sync_quicksight_user_datasources(%s) finished",
        user_sso_ids_to_update,
    )


def _check_tools_access(user):
    if (
        user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()
        and not user.profile.tools_access_role_arn
    ):
        create_tools_access_iam_role_task.delay(user.id)


def create_user_from_sso(
    sso_id,
    primary_email,
    first_name,
    last_name,
    sso_status,
    check_tools_access_if_user_exists,
):
    user_model = get_user_model()
    try:
        user = get_user_by_sso_id(sso_id)
    except user_model.DoesNotExist:
        # If the user doesn't exist we will have to create it
        user = user_model.objects.create(
            username=sso_id,
            email=primary_email,
        )
        user.profile.sso_id = sso_id
        user.profile.sso_status = sso_status
        try:
            user.save()
            logger.info("User %s with email %s has been created", user.username, user.email)
        except IntegrityError:
            # A concurrent request may have overtaken this one and created a user
            user = get_user_by_sso_id(sso_id)

        _check_tools_access(user)
    else:
        if check_tools_access_if_user_exists:
            _check_tools_access(user)

    changed = False

    if user.username != sso_id:
        changed = True
        user.username = sso_id

    if user.email != primary_email:
        changed = True
        user.email = primary_email

    if user.first_name != first_name:
        changed = True
        user.first_name = first_name

    if user.last_name != last_name:
        changed = True
        user.last_name = last_name

    if user.has_usable_password():
        changed = True
        user.set_unusable_password()

    if user.profile.sso_status != sso_status:
        changed = True
        user.profile.sso_status = sso_status

    if changed:
        logger.info("User %s with email %s has changed, saving updates", user.username, user.email)
        user.save()

    return user


@celery_app.task(autoretry_for=(redis.exceptions.LockError,))
@close_all_connections_if_not_in_atomic_block
def sync_s3_sso_users():
    try:
        with cache.lock("sso_sync_last_published_lock", blocking_timeout=0, timeout=1800):
            _do_sync_s3_sso_users()
    except redis.exceptions.LockError:
        logger.info("sync_s3_sso_users: Unable to acquire lock. Not running")


def _do_get_staff_sso_s3_object_summaries(s3_bucket):
    logger.info("sync_s3_sso_users: Reading files from bucket %s", s3_bucket)
    files = s3_bucket.objects.filter(Prefix="data-flow-exports")

    # Get the list of files, oldest first. Process in that order, so any changes in newer files take precedence
    sorted_files = sorted(files, key=lambda x: x.last_modified, reverse=False)
    for file in sorted_files:
        file.source_key = f"s3://{file.bucket_name}/{file.key}"
        logger.info("sync_s3_sso_users: Found S3 file with key %s", file.source_key)
    return sorted_files


def _process_staff_sso_file(client, source_key) -> list[int]:

    seen_user_ids = []

    with smart_open(
        source_key,
        "r",
        transport_params={
            "client": client,
        },
        encoding="utf-8",
    ) as file_input_stream:  # type: ignore
        logger.info("sync_s3_sso_users: Processing file %s", source_key)
        for line in file_input_stream:
            if not line or line == "\n":
                continue

            user = json.loads(line)
            user_obj = user["object"]
            user_id = user_obj.get("dit:StaffSSO:User:userId")

            emails = user_obj.get("dit:emailAddress", [])
            primary_email = user_obj.get("dit:StaffSSO:User:contactEmailAddress") or emails[0]
            first_name = user_obj.get("dit:firstName")
            last_name = user_obj.get("dit:lastName")
            status = user_obj.get("dit:StaffSSO:User:status")

            logger.info(
                "sync_s3_sso_users: Processing user id %s",
                user_id,
            )
            try:
                user = create_user_from_sso(
                    user_id,
                    primary_email,
                    first_name,
                    last_name,
                    status,
                    check_tools_access_if_user_exists=True,
                )

            except IntegrityError:
                logger.exception("sync_s3_sso_users: Failed to create user record")

            seen_user_ids.append(user_id)

    return seen_user_ids


def _get_seen_ids(files, client) -> list[int]:
    seen_user_ids = list[int]()

    for file in files:
        seen_ids_in_file = _process_staff_sso_file(client, file.source_key)
        seen_user_ids.extend(seen_ids_in_file)
    return list(set(seen_user_ids))


def _is_full_sync(files):
    is_full_sync = all("full" in file.key for file in files)
    logger.info("sync_s3_sso_users: is full sync: %s", is_full_sync)
    return is_full_sync


def _do_sync_s3_sso_users():

    logger.info("sync_s3_sso_users: Starting sync of users in S3 file")

    s3_resource = get_s3_resource()
    bucket = s3_resource.Bucket(settings.AWS_UPLOADS_BUCKET)
    files = _do_get_staff_sso_s3_object_summaries(bucket)

    if len(files) > 0:
        seen_ids = _get_seen_ids(files, s3_resource.meta.client)

        if len(seen_ids) > 0 and _is_full_sync(files):
            unseen_user_profiles = (
                Profile.objects.exclude(user__username__in=seen_ids)
                .filter(sso_status="active")
                .select_related("user")
            )
            logger.info(
                "sync_s3_sso_users: active users exist locally but not in SSO %s",
                list(unseen_user_profiles.values_list("user__id", flat=True)),
            )

            unseen_user_profiles.update(sso_status="inactive")

        # At the end of the loop, delete all loaded files
        delete_keys = [{"Key": file.key} for file in files]
        logger.info("sync_s3_sso_users: Deleting keys %s", delete_keys)
        bucket.delete_objects(Delete={"Objects": delete_keys})

        logger.info("sync_s3_sso_users: Finished sync of users in S3 file")

    else:
        logger.info("sync_s3_sso_users: No files to process")


def fetch_visualisation_log_events(log_group, log_stream):
    client = boto3.client("logs")
    events = []
    next_token = None
    while True:
        try:
            response = client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                **{"nextToken": next_token} if next_token else {},
            )
        except ClientError:
            return []
        next_token = response.get("nextForwardToken")
        events += response.get("events", [])
        if next_token is None or not response["events"]:
            break
    return events


def _parse_postgres_log(log_reader, from_date, to_date):
    valid_log_lines = []
    for log_line in log_reader:
        # Ignore non-audit logs
        message = log_line.get("message")
        if message is None or not message.startswith("AUDIT:"):
            continue

        # Read in the pgaudit log message
        log_line.update(
            next(
                csv.DictReader(
                    [",".join([log_line["message"][7:], log_line["connection_from"]])],
                    fieldnames=settings.PGAUDIT_LOG_HEADERS,
                )
            )
        )

        # Some exceptions get through to the logs without a date. Ignore them
        try:
            log_line["log_time"] = datetime.datetime.strptime(
                log_line["log_time"], "%Y-%m-%d %H:%M:%S.%f UTC"
            ).replace(tzinfo=utc)
        except ValueError:
            continue

        if log_line["log_time"] <= from_date or log_line["log_time"] > to_date:
            continue

        # Ignore common noise generated by tools
        if re.match(
            "|".join(settings.PGAUDIT_IGNORE_STATEMENTS_RE),
            " ".join(log_line["statement"].split("\n")).rstrip().lstrip(),
            re.I,
        ):
            continue

        valid_log_lines.append(log_line)

    return valid_log_lines


def _fetch_docker_pgaudit_logs(from_date, to_date):
    log_dir = "/var/log/postgres"
    logs = []
    for filename in os.listdir(log_dir):
        if not filename.endswith(".csv"):
            continue
        path = os.path.join(log_dir, filename)
        last_modified = datetime.datetime.fromtimestamp(os.path.getmtime(path)).replace(tzinfo=utc)
        if last_modified <= from_date or last_modified > to_date:
            continue
        # pylint: disable=unspecified-encoding
        with open(path, "r") as log_fh:
            log_reader = csv.DictReader(log_fh, fieldnames=settings.POSTGRES_LOG_HEADERS)
            logs += _parse_postgres_log(log_reader, from_date, to_date)
    return logs


def _fetch_rds_pgaudit_logs(from_date, to_date):
    client = boto3.client("rds", region_name="eu-west-2")
    logs = []
    for log_file in client.describe_db_log_files(
        DBInstanceIdentifier=settings.DATASETS_DB_INSTANCE_ID,
        FilenameContains="csv",
        FileLastWritten=int(from_date.timestamp() * 1000),
    )["DescribeDBLogFiles"]:
        marker = "0"
        while True:
            resp = client.download_db_log_file_portion(
                DBInstanceIdentifier=settings.DATASETS_DB_INSTANCE_ID,
                LogFileName=log_file["LogFileName"],
                NumberOfLines=1000,
                Marker=marker,
            )
            reader = csv.DictReader(
                resp["LogFileData"].split("\n"),
                fieldnames=settings.POSTGRES_LOG_HEADERS,
            )
            logs += _parse_postgres_log(reader, from_date, to_date)

            marker = resp["Marker"]
            if not resp["AdditionalDataPending"]:
                break

    return logs


def _do_sync_tool_query_logs():
    csv.field_size_limit(2000000)
    from_date = cache.get(
        "query_tool_logs_last_run",
        datetime.datetime.utcnow().replace(tzinfo=utc) - datetime.timedelta(minutes=5),
    )
    to_date = datetime.datetime.utcnow().replace(tzinfo=utc)

    logger.info("Syncing pgaudit logs between %s and %s", from_date, to_date)

    db_name_map = {v["NAME"]: k for k, v in settings.DATABASES.items()}
    databases = Database.objects.all()

    if settings.PGAUDIT_LOG_TYPE == "docker":
        logs = _fetch_docker_pgaudit_logs(from_date, to_date)
    else:
        logs = _fetch_rds_pgaudit_logs(from_date, to_date)

    db_users = DatabaseUser.objects.filter(deleted_date=None)

    for log in logs:
        try:
            database = databases.get(memorable_name=db_name_map.get(log["database_name"]))
        except Database.DoesNotExist:
            logger.info(
                "Skipping log entry for user %s on db %s as the db is not configured",
                log["user_name"],
                log["database_name"],
            )
            continue

        db_user = db_users.filter(username=log["user_name"]).first()
        if not db_user:
            logger.info(
                "Skipping log entry for user %s on db %s (%s) as no matching user could be found",
                log["user_name"],
                log["database_name"],
                log["connection_from"],
            )
            continue

        try:
            audit_log = ToolQueryAuditLog.objects.create(
                user=db_user.owner,
                database=database,
                rolename=log["user_name"],
                query_sql=log["statement"],
                timestamp=log["log_time"],
                connection_from=(
                    log["connection_from"].split(":")[0]
                    if log["connection_from"] is not None
                    else None
                ),
            )
        except IntegrityError:
            logger.info(
                "Skipping duplicate log record for %s at %s", log["user_name"], log["log_time"]
            )
            continue

        # Extract the queried tables
        # There is a chance that the query we are parsing
        # is not parsable by pglast. This creates a lot of noise in the
        # logs so we do not log the errors in this sql to sentry
        tables = extract_queried_tables_from_sql_query(
            audit_log.query_sql.strip().rstrip(";"), log_errors=False
        )
        for table in tables:
            audit_log.tables.create(schema=table[0], table=table[1])

        logger.info(
            "Created log record for user %s in db %s",
            log["user_name"],
            log["database_name"],
        )

    cache.set("query_tool_logs_last_run", to_date)


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def sync_tool_query_logs():
    if waffle.switch_is_active("enable_tool_query_log_sync"):
        try:
            with cache.lock("query_tool_logs_last_run_lock", blocking_timeout=0, timeout=1800):
                _do_sync_tool_query_logs()
        except redis.exceptions.LockError:
            logger.info("Unable to acquire lock to sync tool query logs")


def _send_slack_message(text):
    if settings.SLACK_SENTRY_CHANNEL_WEBHOOK is not None:
        response = requests.post(
            settings.SLACK_SENTRY_CHANNEL_WEBHOOK,
            json={"text": text},
        )
        response.raise_for_status()


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def long_running_query_alert():
    if waffle.switch_is_active("enable_long_running_query_alerts"):
        interval = settings.LONG_RUNNING_QUERY_ALERT_THRESHOLD
        logger.info("Checking for queries running longer than %s on the datasets db.", interval)
        with connections[settings.EXPLORER_DEFAULT_CONNECTION].cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pg_stat_activity
                WHERE (now() - pg_stat_activity.query_start) > interval '{interval}'
                AND state = 'active'
                """
            )
            query_count = int(cursor.fetchone()[0])
            if query_count > 0:
                message = (
                    f':rotating_light: Found {query_count} SQL quer{"y" if query_count == 1 else "ies"}'
                    f" running for longer than {interval} on the datasets db."
                )
                logger.info(message)
                _send_slack_message(message)
            else:
                logger.info("No long running queries found.")


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def push_tool_monitoring_dashboard_datasets():
    try:
        with cache.lock(
            "push_tool_monitoring_dashboard_datasets", blocking_timeout=0, timeout=3600
        ):
            do_push_tool_monitoring_dashboard_datasets()
    except redis.exceptions.LockError as e:
        logger.warning("Failed to acquire lock for push_tool_monitoring_dashboard_datasets: %s", e)


def do_push_tool_monitoring_dashboard_datasets():
    geckboard_api_key = os.environ["GECKOBOARD_API_KEY"]
    cluster = os.environ["APPLICATION_SPAWNER_OPTIONS__FARGATE__VISUALISATION__CLUSTER_NAME"]
    task_role_prefix = os.environ["APPLICATION_TEMPLATES__1__SPAWNER_OPTIONS__ROLE_PREFIX"]
    geckoboard_endpoint = (
        f'https://api.geckoboard.com/datasets/data-workspace.{os.environ["ENVIRONMENT"]}.'
    )

    def report_running_tools(client, session):
        pending_task_arns = client.list_tasks(cluster=cluster, desiredStatus="RUNNING")["taskArns"]

        pending_tasks = (
            client.describe_tasks(cluster=cluster, tasks=pending_task_arns)["tasks"]
            if pending_task_arns
            else []
        )

        running_tasks = [t for t in pending_tasks if t["lastStatus"] == "RUNNING"]

        # Create dataset
        payload = {"fields": {"count": {"type": "number", "name": "Count"}}}
        session.put(
            geckoboard_endpoint + "tools.running",
            json=payload,
        )

        # Add data
        payload = {"data": [{"count": len(running_tasks)}]}
        session.put(
            geckoboard_endpoint + "tools.running/data",
            json=payload,
        )

    def report_failed_tools(client, session):
        stopped_tasks_arns = client.list_tasks(cluster=cluster, desiredStatus="STOPPED")[
            "taskArns"
        ]

        stopped_tasks = (
            client.describe_tasks(cluster=cluster, tasks=stopped_tasks_arns)["tasks"]
            if stopped_tasks_arns
            else []
        )

        # Create dataset
        payload = {
            "fields": {
                "user": {"type": "string", "name": "User"},
                "tool": {"type": "string", "name": "Tool"},
                "time_started": {"type": "datetime", "name": "Time started"},
                "stopped_reason": {"type": "string", "name": "Reason"},
            }
        }
        session.put(
            geckoboard_endpoint + "tools.failed",
            json=payload,
        )

        # Add data
        payload = {
            "data": [
                {
                    "user": t["overrides"]["taskRoleArn"][31:].replace(task_role_prefix, ""),
                    "tool": t["group"].replace(f'family:{cluster.replace("-notebooks", "")}-', "")[
                        :-9
                    ],
                    "time_started": t["createdAt"].isoformat(),
                    "stopped_reason": t["stoppedReason"],
                }
                for t in stopped_tasks
                if t["stoppedReason"] != "Task stopped by user"
            ]
        }
        session.put(
            geckoboard_endpoint + "tools.failed/data",
            json=payload,
        )

    def report_tool_average_start_times(client, session):
        pending_task_arns = client.list_tasks(cluster=cluster, desiredStatus="RUNNING")["taskArns"]

        pending_tasks = (
            client.describe_tasks(cluster=cluster, tasks=pending_task_arns)["tasks"]
            if pending_task_arns
            else []
        )

        running_tasks = [t for t in pending_tasks if t["lastStatus"] == "RUNNING"]

        # Create dataset
        payload = {
            "fields": {
                "time_taken": {
                    "type": "duration",
                    "time_unit": "seconds",
                    "name": "Time Taken",
                },
                "hour_of_day": {"type": "string", "name": "Hour"},
            }
        }
        session.put(
            geckoboard_endpoint + "tools.durations",
            json=payload,
        )

        # Add data
        payload = {
            "data": [
                {
                    "time_taken": (t["startedAt"] - t["createdAt"]).seconds,
                    "hour_of_day": t["startedAt"].strftime("%H"),
                }
                for t in running_tasks
            ]
        }

        hours = {t["hour_of_day"] for t in payload["data"]}

        # Create a bucket for each hour
        for x in range(24):
            if str(x) not in hours:
                payload["data"].append(
                    {
                        "time_taken": 0,
                        "hour_of_day": datetime.datetime(2021, 1, 1, x, 0, 0).strftime("%H"),
                    }
                )

        session.put(
            geckoboard_endpoint + "tools.durations/data",
            json=payload,
        )

    def report_recent_tool_start_times(client, session):
        pending_task_arns = client.list_tasks(cluster=cluster, desiredStatus="RUNNING")["taskArns"]

        pending_tasks = (
            client.describe_tasks(cluster=cluster, tasks=pending_task_arns)["tasks"]
            if pending_task_arns
            else []
        )

        running_tasks = [t for t in pending_tasks if t["lastStatus"] == "RUNNING"]

        # Create dataset
        payload = {
            "fields": {
                "user": {"type": "string", "name": "User"},
                "tool": {"type": "string", "name": "Tool"},
                "time_started": {"type": "datetime", "name": "Time started"},
                "time_taken": {
                    "type": "duration",
                    "time_unit": "seconds",
                    "name": "Time Taken",
                },
            }
        }
        session.put(
            geckoboard_endpoint + "tools.recent",
            json=payload,
        )

        # Add data
        payload = {
            "data": [
                {
                    "user": t["overrides"]["taskRoleArn"][31:].replace(task_role_prefix, ""),
                    "tool": t["group"].replace(f'family:{cluster.replace("-notebooks", "")}-', "")[
                        :-9
                    ],
                    "time_started": t["createdAt"].isoformat(),
                    "time_taken": (t["startedAt"] - t["createdAt"]).seconds,
                }
                for t in sorted(running_tasks, key=lambda x: x["startedAt"], reverse=True)[:10]
            ]
        }

        session.put(
            geckoboard_endpoint + "tools.recent/data",
            json=payload,
        )

    client = boto3.client("ecs")

    session = requests.Session()
    session.auth = (geckboard_api_key, "")

    report_running_tools(client, session)
    report_failed_tools(client, session)
    report_tool_average_start_times(client, session)
    report_recent_tool_start_times(client, session)


def _run_duplicate_tools_monitor():
    client = boto3.client("ecs")
    cluster = os.environ["APPLICATION_SPAWNER_OPTIONS__FARGATE__VISUALISATION__CLUSTER_NAME"]

    # Get a list of all running or spawning tasks
    task_arns = []
    next_token = ""
    while True:
        tasks_response = client.list_tasks(
            cluster=cluster, desiredStatus="RUNNING", nextToken=next_token
        )
        task_arns.extend(tasks_response["taskArns"])
        next_token = tasks_response.get("nextToken")
        if not next_token:
            break

    total_running_tasks = len(task_arns)
    logger.info("Found %d running tasks on cluster %s", total_running_tasks, cluster)

    def paginate(records):
        for i in range(0, len(records), 100):
            yield records[i : i + 100]

    # Group running tasks by their task definition arn
    task_details = defaultdict(list)
    for chunk in paginate(task_arns):
        for description in client.describe_tasks(cluster=cluster, tasks=chunk)["tasks"]:
            if "startedAt" not in description:
                continue
            task_details[description["taskDefinitionArn"].split("/")[-1].split(":")[0]].append(
                {"started": description["startedAt"], "arn": description["taskArn"]}
            )

    total_unique_running_task_arns = len(task_details)
    logger.info(
        "Found %d unique task definitions (out of %d running tasks)",
        total_unique_running_task_arns,
        total_running_tasks,
    )

    # Loop through task definitions, if any definition has more than one running task,
    # stop all but the task with the latest started date
    stop_count = 0
    for task_def_arn, task_details in task_details.items():
        if len(task_details) <= 1:
            continue
        running_tasks = sorted(task_details, key=lambda x: x["started"])
        tasks_to_stop = running_tasks[:-1]
        logger.info(
            "Task def %s has %d running tasks. Will stop %d of them",
            task_def_arn,
            len(running_tasks),
            len(tasks_to_stop),
        )
        for task in tasks_to_stop:
            if waffle.switch_is_active("force_stop_duplicate_running_tasks"):
                logger.info("Stopping task %s which started at %s", task["arn"], task["started"])
                client.stop_task(cluster=cluster, task=task["arn"])
            else:
                logger.info(
                    "Task %s which started at %s would be stopped", task["arn"], task["started"]
                )
            stop_count += 1

        logger.info(
            "Left one running task %s which started at %s",
            running_tasks[-1]["arn"],
            running_tasks[-1]["started"],
        )

    message = f"Found {stop_count} duplicate tasks running on cluster {cluster}."
    if stop_count > 0:
        logger.error(message)
        _send_slack_message(":rotating_light: " + message)
    else:
        logger.info(message)


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def duplicate_tools_monitor():
    try:
        with cache.lock("duplicate_tools_monitor", blocking_timeout=0, timeout=1800):
            _run_duplicate_tools_monitor()
    except redis.exceptions.LockError:
        logger.info("duplicate_tools_alert: Unable to acquire lock to monitor for duplicate tools")


def _run_orphaned_tools_monitor():
    """
    Find and stop any running application instances that meet one of:

    1. Is owned by a user that does not have tool access
    2. Has `None` as a task_arn
    3. Does not have a running task on ECS
    """
    tools = ApplicationInstance.objects.filter(
        spawner="FARGATE",
        state="RUNNING",
        created_date__lt=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=2),
    )
    for tool in tools:
        is_tool = tool.application_template.application_type == "TOOL"
        cluster = json.loads(tool.spawner_application_template_options)["CLUSTER_NAME"]
        task_arn = json.loads(tool.spawner_application_instance_id).get("task_arn")

        # If the application instance is running but the task arn is null mark it as stopped
        if task_arn is None:
            logger.info("orphaned_tools_monitor: Stopping tool due to null task arn %s", tool)
            tool.state = "STOPPED"
            tool.single_running_or_spawning_integrity = str(tool.id)
            tool.save(update_fields=["state", "single_running_or_spawning_integrity"])
            continue

        # If the user who started the tool does not have tool access stop the tool
        if is_tool and not tool.owner.has_perm("applications.start_all_applications"):
            logger.info(
                "orphaned_tools_monitor: Stopping tool due to user not having permission %s", tool
            )
            try:
                _fargate_task_stop(cluster, task_arn)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "orphaned_tools_monitor: Failed to stop illegally running tool %s", tool
                )
            continue

        # If the tool doesn't exist on ECS we should mark it as stopped locally
        try:
            task = _fargate_task_describe(cluster, task_arn)
        except Exception:  # pylint: disable=broad-except
            logger.exception("orphaned_tools_monitor: failed to describe task for tool %s", tool)
            continue

        if task is None:
            logger.info(
                "orphaned_tools_monitor: Marking tool as stopped as no task exists on ECS %s",
                tool,
            )
            tool.state = "STOPPED"
            tool.single_running_or_spawning_integrity = str(tool.id)
            tool.save(update_fields=["state", "single_running_or_spawning_integrity"])
            continue


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def orphaned_tools_monitor():
    if not waffle.switch_is_active("enable_orphaned_tools_monitor"):
        logger.info("orphaned_tools_monitor: Skipping run as waffle switch is inactive")
        return
    try:
        with cache.lock("orphaned_tools_monitor", blocking_timeout=0, timeout=1800):
            _run_orphaned_tools_monitor()
    except redis.exceptions.LockError:
        logger.info(
            "orphaned_tools_monitor: Unable to acquire lock to monitor for duplicate tools"
        )


def get_tool_url_for_user(user: get_user_model(), application_template: ApplicationTemplate):
    user_prefix = stable_identification_suffix(str(user.profile.sso_id), short=True)
    hostname = application_template.host_basename
    return f"https://{hostname}-{user_prefix}.{settings.APPLICATION_ROOT_DOMAIN}/"


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def remove_tools_access_for_users_with_expired_cert():
    try:
        with cache.lock(
            "_remove_tools_access_for_users_with_expired_cert", blocking_timeout=0, timeout=1800
        ):
            _remove_tools_access_for_users_with_expired_cert()
    except redis.exceptions.LockNotOwnedError:
        logger.info("remove_tools_access: Lock not owned - running on another instance?")
    except redis.exceptions.LockError:
        logger.info("remove_tools_access: Unable to grab lock - running on another instance?")


def _remove_tools_access_for_users_with_expired_cert():
    logger.info("_remove_tools_access: Start")
    user_model = get_user_model()
    permissions_codenames = [
        "start_all_applications",
        "develop_visualisations",
        "access_quicksight",
        "access_appstream",
    ]
    permission_ids = Permission.objects.filter(codename__in=permissions_codenames).all()

    def remove_tools_access(user):
        for permission_id in permission_ids:
            user.user_permissions.remove(permission_id.id)

    for user in user_model.objects.all():
        user_has_access = user.user_permissions.filter(codename__in=permissions_codenames).exists()
        user_profile = Profile.objects.filter(user=user.id)

        if user_has_access and user_profile[0].tools_certification_date:
            if has_tools_cert_expired(user_profile[0].tools_certification_date):
                remove_tools_access(user)

    logger.info("_remove_tools_access: End")


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def self_certify_renewal_email_notification():
    try:
        with cache.lock(
            "_self_certify_renewal_email_notification", blocking_timeout=0, timeout=1800
        ):
            _self_certify_renewal_email_notification()
    except redis.exceptions.LockNotOwnedError:
        logger.info("send_notify_email: Lock not owned - running on another instance?")
    except redis.exceptions.LockError:
        logger.info("send_notify_email: Unable to grab lock - running on another instance?")


def _self_certify_renewal_email_notification():
    logger.info("_self_certify_renewal_email_notification: Start")

    def send_notify_email(user, user_profile):
        logger.info(
            "send_notification_emails: Sending notification for self certify renewal for  %s",
            user.email,
        )
        try:
            send_email(
                template_id=settings.NOTIFY_SELF_CERTIFY_RENEWAL_TEMPLATE_ID,
                email_address=user.email,
            )
        except EmailSendFailureException:
            logger.exception("Failed to send email")
        else:
            user_profile.is_renewal_email_sent = True
            user_profile.save()
            logger.info(
                "send_notification_emails: is_renewal_email_sent for %s is set",
                user.email,
            )

    for user_profile in Profile.objects.filter(is_renewal_email_sent=False).select_related("user"):
        if is_tools_cert_renewal_due(user_profile.tools_certification_date):
            send_notify_email(user_profile.user, user_profile)
    logger.info("_self_certify_renewal_email_notification: Stop")
