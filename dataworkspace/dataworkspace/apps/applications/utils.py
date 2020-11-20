import datetime
import json
import logging
import urllib.parse
from typing import Dict, List

import boto3
import botocore
from botocore.exceptions import ClientError
from django_db_geventpool.utils import close_connection
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Q
import gevent
from psycopg2 import connect, sql
import requests
from mohawk import Sender
import redis

from dataworkspace.apps.applications.spawner import (
    get_spawner,
    stop,
    _fargate_task_describe,
)
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    ApplicationInstanceDbUsers,
    ApplicationTemplate,
)
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    create_tools_access_iam_role,
    database_dsn,
    stable_identification_suffix,
    source_tables_for_user,
    new_private_database_credentials,
    postgres_user,
)
from dataworkspace.apps.applications.gitlab import gitlab_has_developer_access
from dataworkspace.apps.datasets.models import (
    VisualisationCatalogueItem,
    VisualisationLink,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.cel import celery_app

logger = logging.getLogger('app')


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
    possible_host_basename, _, host_basename_or_commit_id = public_host.rpartition('--')
    if possible_host_basename and is_8_char_hex(host_basename_or_commit_id):
        host_basename = possible_host_basename
        commit_id = host_basename_or_commit_id
    else:
        host_basename = public_host
        commit_id = None

    # The value after the rightmost '-', if it's there, is the user id
    possible_host_basename, _, host_basename_or_user = host_basename.rpartition('-')
    if possible_host_basename and is_8_char_hex(host_basename_or_user):
        host_basename = possible_host_basename
        user = host_basename_or_user
    else:
        user = None

    matching_tools = (
        list(
            ApplicationTemplate.objects.filter(
                application_type='TOOL', host_basename=host_basename
            )
        )
        if user
        else []
    )

    matching_visualisations = (
        list(
            ApplicationTemplate.objects.filter(
                application_type='VISUALISATION', host_basename=host_basename
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
        raise Exception('Too many ApplicatinTemplate matching host')

    return (matching[0], tag, user, commit_id)


def application_options(application_template):
    common_spawner_options = settings.APPLICATION_SPAWNER_OPTIONS.get(
        application_template.spawner, {}
    ).get(application_template.application_type, {})

    return {
        **common_spawner_options,
        **json.loads(application_template.spawner_options),
    }


def api_application_dict(application_instance):
    spawner_state = get_spawner(
        application_instance.application_template.spawner
    ).state(
        application_instance.spawner_application_template_options,
        application_instance.created_date.replace(tzinfo=None),
        application_instance.spawner_application_instance_id,
        application_instance.public_host,
    )

    # Only pass through the database state if the spawner is running,
    # Otherwise, we are in an error condition, and so return the spawner
    # state, so the client (i.e. the proxy) knows to take action
    api_state = (
        application_instance.state if spawner_state == 'RUNNING' else spawner_state
    )

    sso_id_hex_short = stable_identification_suffix(
        str(application_instance.owner.profile.sso_id), short=True
    )

    return {
        'proxy_url': application_instance.proxy_url,
        'state': api_state,
        'user': sso_id_hex_short,
        'wrap': application_instance.application_template.wrap,
        # Used by metrics to label the application
        'name': application_instance.application_template.nice_name,
    }


def get_api_visible_application_instance_by_public_host(public_host):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.get(
        public_host=public_host, state__in=['RUNNING', 'SPAWNING']
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
    if application_template.application_type == 'VISUALISATION':
        visualisation_catalogue_item = VisualisationCatalogueItem.objects.get(
            visualisation_template=application_template
        )

    request_sso_id_hex_short = stable_identification_suffix(
        str(request.user.profile.sso_id), short=True
    )
    is_preview = commit_id is not None

    def is_tool_and_correct_user_and_allowed_to_start():
        return (
            application_template.application_type == 'TOOL'
            and host_user == request_sso_id_hex_short
            and request.user.has_perm('applications.start_all_applications')
        )

    def is_published_visualisation_and_requires_authentication():
        return (
            not is_preview
            and application_template.visible is True
            and visualisation_catalogue_item
            and visualisation_catalogue_item.user_access_type
            == 'REQUIRES_AUTHENTICATION'
        )

    def is_published_visualisation_and_requires_authorisation_and_has_authorisation():
        return (
            not is_preview
            and application_template.visible is True
            and visualisation_catalogue_item
            and visualisation_catalogue_item.user_access_type
            == 'REQUIRES_AUTHORIZATION'
            and request.user.visualisationuserpermission_set.filter(
                visualisation=visualisation_catalogue_item
            ).exists()
        )

    def is_visualisation_preview_and_has_gitlab_developer():
        return (
            is_preview
            and visualisation_catalogue_item
            and gitlab_has_developer_access(
                request.user, application_template.gitlab_project_id
            )
        )

    return (
        is_tool_and_correct_user_and_allowed_to_start()
        or is_published_visualisation_and_requires_authentication()
        or is_published_visualisation_and_requires_authorisation_and_has_authorisation()
        or is_visualisation_preview_and_has_gitlab_developer()
    )


def stop_spawner_and_application(application_instance):
    stop.delay(application_instance.spawner, application_instance.id)
    set_application_stopped(application_instance)


def set_application_stopped(application_instance):
    application_instance.state = 'STOPPED'
    application_instance.single_running_or_spawning_integrity = str(
        application_instance.id
    )
    application_instance.save(
        update_fields=['state', 'single_running_or_spawning_integrity']
    )


def application_instance_max_cpu(application_instance):
    # If we don't have the proxy url yet, we can't have any metrics yet.
    # This is expected and should not be shown as an error
    if application_instance.proxy_url is None:
        raise ExpectedMetricsException('Unknown')

    instance = urllib.parse.urlsplit(application_instance.proxy_url).hostname + ':8889'
    url = f'https://{settings.PROMETHEUS_DOMAIN}/api/v1/query'
    params = {
        'query': f'increase(precpu_stats__cpu_usage__total_usage{{instance="{instance}"}}[30s])[2h:30s]'
    }
    try:
        response = requests.get(url, params)
    except requests.RequestException:
        raise UnexpectedMetricsException('Error connecting to metrics server')

    response_dict = response.json()
    if response_dict['status'] != 'success':
        raise UnexpectedMetricsException(
            f'Metrics server return value is {response_dict["status"]}'
        )

    try:
        values = response_dict['data']['result'][0]['values']
    except (IndexError, KeyError):
        # The server not having metrics yet should not be reported as an error
        raise ExpectedMetricsException('Unknown')

    max_cpu = 0.0
    ts_at_max = 0
    for ts, cpu in values:
        cpu_float = float(cpu) / (1_000_000_000 * 30) * 100
        if cpu_float >= max_cpu:
            max_cpu = cpu_float
            ts_at_max = ts

    return max_cpu, ts_at_max


@celery_app.task()
@close_connection
def kill_idle_fargate():
    logger.info('kill_idle_fargate: Start')

    two_hours_ago = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=-2
    )
    instances = ApplicationInstance.objects.filter(
        spawner='FARGATE',
        state__in=['RUNNING', 'SPAWNING'],
        created_date__lt=two_hours_ago,
    )

    for instance in instances:
        if instance.state == 'SPAWNING':
            stop_spawner_and_application(instance)
            continue

        logger.info('kill_idle_fargate: Attempting to find CPU usage of %s', instance)
        try:
            max_cpu, _ = application_instance_max_cpu(instance)
        except ExpectedMetricsException:
            logger.info('kill_idle_fargate: Unable to find CPU usage for %s', instance)
            continue
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'kill_idle_fargate: Unable to find CPU usage for %s', instance
            )
            continue

        logger.info('kill_idle_fargate: CPU usage for %s is %s', instance, max_cpu)

        if max_cpu >= 1.0:
            continue

        try:
            stop_spawner_and_application(instance)
        except Exception:  # pylint: disable=broad-except
            logger.exception('kill_idle_fargate: Unable to stop %s', instance)

        logger.info('kill_idle_fargate: Stopped application %s', instance)

    logger.info('kill_idle_fargate: End')


@celery_app.task()
@close_connection
def populate_created_stopped_fargate():
    logger.info('populate_created_stopped_fargate: Start')

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
                spawner='FARGATE',
                created_date__gte=start_of_range,
                created_date__lt=end_of_range,
            )
            & (Q(spawner_created_at__isnull=True) | Q(spawner_stopped_at__isnull=True))
        ).order_by('-created_date')

        for instance in instances:
            logger.info('populate_created_stopped_fargate checking: %s', instance)

            try:
                options = json.loads(instance.spawner_application_template_options)
                cluster_name = options['CLUSTER_NAME']
                task_arn = json.loads(instance.spawner_application_instance_id)[
                    'task_arn'
                ]
            except (ValueError, KeyError):
                continue

            if not task_arn:
                continue

            # To not bombard the ECS API
            gevent.sleep(0.1)
            try:
                task = _fargate_task_describe(cluster_name, task_arn)
            except Exception:  # pylint: disable=broad-except
                logger.exception('populate_created_stopped_fargate %s', instance)
                gevent.sleep(10)
                continue

            if not task:
                logger.info(
                    'populate_created_stopped_fargate no task found %s %s',
                    instance,
                    task_arn,
                )
                continue

            update_fields = []
            if 'createdAt' in task and instance.spawner_created_at is None:
                instance.spawner_created_at = task['createdAt']
                update_fields.append('spawner_created_at')

            if 'stoppedAt' in task and instance.spawner_stopped_at is None:
                instance.spawner_stopped_at = task['stoppedAt']
                update_fields.append('spawner_stopped_at')

            if update_fields:
                logger.info(
                    'populate_created_stopped_fargate saving: %s %s',
                    instance,
                    update_fields,
                )
                instance.save(update_fields=update_fields)

    logger.info('populate_created_stopped_fargate: End')


@celery_app.task()
@close_connection
def delete_unused_datasets_users():
    try:
        with cache.lock(
            "delete_unused_datasets_users", blocking_timeout=0, timeout=1800
        ):
            _do_delete_unused_datasets_users()
    except redis.exceptions.LockError:
        logger.info(
            "delete_unused_datasets_users: Unable to grab lock - running on another instance?"
        )


def _do_delete_unused_datasets_users():
    logger.info('delete_unused_datasets_users: Start')

    for memorable_name, database_data in settings.DATABASES_DATA.items():
        database_obj = Database.objects.get(memorable_name=memorable_name)
        database_name = database_data['NAME']

        with connect(database_dsn(database_data)) as conn, conn.cursor() as cur:
            logger.info('delete_unused_datasets_users: finding database users')
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
                )
                OR
                (
                    valuntil != 'infinity'
                    AND valuntil < now()
                    AND usename LIKE 'user_%' AND
                    (
                        usename LIKE '%_qs'
                        OR usename LIKE '%_explorer'
                    )
                )
                ORDER BY usename;
                """
            )
            usenames = [result[0] for result in cur.fetchall()]

            logger.info('delete_unused_datasets_users: finding schemas')
            cur.execute(
                """
                SELECT nspname FROM pg_catalog.pg_namespace WHERE
                nspname != 'pg_catalog' AND nspname != 'information_schema'
                ORDER BY nspname
            """
            )
            schemas = [result[0] for result in cur.fetchall()]

        logger.info(
            'delete_unused_datasets_users: waiting in case they were just created'
        )
        gevent.sleep(15)

        # We want to be able to delete db users created, but then _not_ associated with an
        # running application, such as those from a STOPPED application, but also from those
        # that were created but then the server went down before the application was created.
        in_use_usenames = set(
            ApplicationInstanceDbUsers.objects.filter(
                db=database_obj,
                db_username__in=usenames,
                application_instance__state__in=['RUNNING', 'SPAWNING'],
            ).values_list('db_username', flat=True)
        )
        not_in_use_usernames = [
            usename for usename in usenames if usename not in in_use_usenames
        ]

        schema_revokes = [
            'REVOKE USAGE ON SCHEMA {} FROM {};',
            'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {};',
            'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} FROM {};',
            'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {} FROM {};',
            'ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL PRIVILEGES ON TABLES FROM {}',
            'ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL PRIVILEGES ON SEQUENCES FROM {}',
            'ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL PRIVILEGES ON FUNCTIONS FROM {}',
        ]

        with connect(database_dsn(database_data)) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                for usename in not_in_use_usernames:
                    try:
                        logger.info(
                            'delete_unused_datasets_users: revoking credentials for %s',
                            usename,
                        )

                        # Multiple concurrent GRANT CONNECT on the same database can cause
                        # "tuple concurrently updated" errors
                        lock_name = f'database-grant-connect-{database_name}--v4'
                        with cache.lock(lock_name, blocking_timeout=3, timeout=180):
                            cur.execute(
                                sql.SQL(
                                    'REVOKE CONNECT ON DATABASE {} FROM {};'
                                ).format(
                                    sql.Identifier(database_name),
                                    sql.Identifier(usename),
                                )
                            )

                            cur.execute(
                                sql.SQL(
                                    'REVOKE ALL PRIVILEGES ON DATABASE {} FROM {};'
                                ).format(
                                    sql.Identifier(database_name),
                                    sql.Identifier(usename),
                                )
                            )

                        for schema in schemas:
                            lock_name = f'database-grant--{database_name}--{schema}--v4'
                            with cache.lock(lock_name, blocking_timeout=3, timeout=180):
                                for schema_revoke in schema_revokes:
                                    try:
                                        cur.execute(
                                            sql.SQL(schema_revoke).format(
                                                sql.Identifier(schema),
                                                sql.Identifier(usename),
                                            )
                                        )
                                    except Exception:  # pylint: disable=broad-except
                                        # This is likely to happen for private schemas where the current user
                                        # does not have revoke privileges. We carry on in a best effort
                                        # to remove the user
                                        logger.info(
                                            'delete_unused_datasets_users: Unable to %s %s %s',
                                            schema_revoke,
                                            schema,
                                            usename,
                                        )

                        logger.info(
                            'delete_unused_datasets_users: dropping user %s', usename
                        )
                        cur.execute(
                            sql.SQL('DROP USER {};').format(sql.Identifier(usename))
                        )
                    except redis.exceptions.LockError:
                        logger.exception('LOCK: Unable to acquire %s', lock_name)

                    except Exception:  # pylint: disable=broad-except
                        logger.exception(
                            'delete_unused_datasets_users: Failed deleting %s', usename
                        )
                    else:
                        logger.info(
                            'delete_unused_datasets_users: revoked credentials for and dropped %s',
                            usename,
                        )

    logger.info('delete_unused_datasets_users: End')


def get_quicksight_dashboard_name_url(dashboard_id, user):
    user_region = settings.QUICKSIGHT_USER_REGION
    embed_role_arn = settings.QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN
    embed_role_name = embed_role_arn.rsplit('/', 1)[1]

    sts = boto3.client('sts')
    account_id = sts.get_caller_identity().get('Account')

    role_credentials = sts.assume_role(
        RoleArn=embed_role_arn, RoleSessionName=user.email
    )['Credentials']

    session = boto3.Session(
        aws_access_key_id=role_credentials['AccessKeyId'],
        aws_secret_access_key=role_credentials['SecretAccessKey'],
        aws_session_token=role_credentials['SessionToken'],
    )

    # QuickSight manages users in a separate region to our data/dashboards.
    qs_user_client = session.client('quicksight', region_name=user_region)
    qs_dashboard_client = session.client('quicksight')

    try:
        qs_user_client.register_user(
            AwsAccountId=account_id,
            Namespace='default',
            IdentityType='IAM',
            IamArn=embed_role_arn,
            UserRole='READER',
            SessionName=user.email,
            Email=user.email,
        )
    except qs_user_client.exceptions.ResourceExistsException:
        pass

    attempts = 5
    while attempts > 0:
        attempts -= 1
        try:
            qs_user_client.create_group_membership(
                AwsAccountId=account_id,
                Namespace='default',
                GroupName=settings.QUICKSIGHT_DASHBOARD_GROUP,
                MemberName=f'{embed_role_name}/{user.email}',
            )
            break

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                if attempts > 0:
                    gevent.sleep(5 - attempts)
                else:
                    raise e
            else:
                raise e

    dashboard_name = qs_dashboard_client.describe_dashboard(
        AwsAccountId=account_id, DashboardId=dashboard_id, AliasName='$PUBLISHED'
    )['Dashboard']['Name']
    dashboard_url = qs_dashboard_client.get_dashboard_embed_url(
        AwsAccountId=account_id,
        DashboardId=dashboard_id,
        IdentityType='QUICKSIGHT',
        UserArn=f'arn:aws:quicksight:{user_region}:{account_id}:user/default/{embed_role_name}/{user.email}',
    )['EmbedUrl']

    return dashboard_name, dashboard_url


def create_update_delete_quicksight_user_data_sources(
    data_client, account_id, quicksight_user, creds
):
    env = settings.ENVIRONMENT.lower()
    qs_datasource_perms = [
        'quicksight:DescribeDataSource',
        'quicksight:DescribeDataSourcePermissions',
        'quicksight:PassDataSource',
    ]

    def _get_data_source_id(db_name):
        return (
            "data-workspace-"
            + env
            + "-"
            + db_name
            + "-"
            + stable_identification_suffix(quicksight_user['Arn'], short=True)
        )

    authorized_data_source_ids = set()

    # Create/update any data sources the user has access to
    for cred in creds:
        db_name = cred['memorable_name']
        data_source_id = _get_data_source_id(db_name)
        data_source_name = f"Data Workspace - {db_name}"
        if env != "production":
            data_source_name = f"{env.upper()} - {data_source_name}"

        create_and_update_params = dict(
            AwsAccountId=account_id,
            DataSourceId=data_source_id,
            Name=data_source_name,
            DataSourceParameters={
                "AuroraPostgreSqlParameters": {
                    "Host": cred['db_host'],
                    "Port": int(cred['db_port']),
                    "Database": cred['db_name'],
                }
            },
            Credentials={
                "CredentialPair": {
                    "Username": cred['db_user'],
                    "Password": cred['db_password'],
                }
            },
            VpcConnectionProperties={"VpcConnectionArn": settings.QUICKSIGHT_VPC_ARN},
        )

        logger.info("-> Creating data source: %s", data_source_id)

        try:
            data_client.create_data_source(
                **create_and_update_params,
                Type='AURORA_POSTGRESQL',
                Permissions=[
                    {
                        'Principal': quicksight_user['Arn'],
                        'Actions': qs_datasource_perms,
                    }
                ],
            )
            logger.info("-> Created: %s", data_source_id)

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceExistsException':
                logger.info(
                    "-> Data source already exists: %s. Updating ...", data_source_id
                )
                data_client.update_data_source(**create_and_update_params)
                logger.info("-> Updated data source: %s", data_source_id)

            else:
                raise e

        authorized_data_source_ids.add(data_source_id)

    # Delete any data sources the user no longer has access to
    all_data_source_ids = {
        _get_data_source_id(db_name) for db_name in settings.DATABASES_DATA.keys()
    }
    unauthorized_data_source_ids = all_data_source_ids - {
        _get_data_source_id(cred['memorable_name']) for cred in creds
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
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                pass

            else:
                raise e


def sync_quicksight_users(data_client, user_client, account_id, quicksight_user_list):
    for quicksight_user in quicksight_user_list:
        user_arn = quicksight_user['Arn']
        user_email = quicksight_user['Email']
        user_role = quicksight_user['Role']
        user_username = quicksight_user['UserName']

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
                            Namespace='default',
                            Role=user_role,
                            UnapplyCustomPermissions=True,
                            UserName=user_username,
                            Email=user_email,
                        )
                    else:
                        user_client.update_user(
                            AwsAccountId=account_id,
                            Namespace="default",
                            Role=user_role,
                            CustomPermissionsName=settings.QUICKSIGHT_AUTHOR_CUSTOM_PERMISSIONS,
                            UserName=user_username,
                            Email=user_email,
                        )

                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        continue  # Can be raised if the user has been deactivated/"deleted"

                    raise e

                dw_user = get_user_model().objects.filter(email=user_email).first()
                if not dw_user:
                    logger.info(
                        "Skipping %s - cannot match with Data Workspace user.",
                        user_email,
                    )
                    continue

                # We technically ignore the case for where a single email has multiple matches on DW, but I'm not
                # sure this is a case that can happen - and if it can, we don't care while prototyping.
                logger.info("Syncing QuickSight resources for %s", dw_user)

                source_tables = source_tables_for_user(dw_user)
                db_role_schema_suffix = stable_identification_suffix(
                    user_arn, short=True
                )

                # This creates a DB user for each of our datasets DBs. These users are intended to be long-lived,
                # so they might already exist. If this is the case, we still generate a new password, as at the moment
                # these user accounts only last for 31 days by default - so we need to update the password to keep them
                # from expiring.
                creds = new_private_database_credentials(
                    db_role_schema_suffix,
                    source_tables,
                    postgres_user(user_email, suffix='qs'),
                    valid_for=datetime.timedelta(
                        days=7
                    ),  # We refresh these creds every night, so they don't need to last long at all.
                )

                create_update_delete_quicksight_user_data_sources(
                    data_client, account_id, quicksight_user, creds
                )

        except redis.exceptions.LockError:
            logger.exception(
                "Unable to sync permissions for %s", quicksight_user['Arn']
            )


@celery_app.task()
def sync_quicksight_permissions(
    user_sso_ids_to_update=tuple(), poll_for_user_creation=False
):
    logger.info(
        'sync_quicksight_user_datasources(%s, poll_for_user_creation=%s) started',
        user_sso_ids_to_update,
        poll_for_user_creation,
    )

    # QuickSight manages users in a single specific regions
    user_client = boto3.client(
        'quicksight', region_name=settings.QUICKSIGHT_USER_REGION
    )
    # Data sources can be in other regions - so here we use the Data Workspace default from its env vars.
    data_client = boto3.client('quicksight')

    account_id = boto3.client('sts').get_caller_identity().get('Account')

    quicksight_user_list: List[Dict[str, str]]
    if len(user_sso_ids_to_update) > 0:
        quicksight_user_list = []

        for user_sso_id in user_sso_ids_to_update:
            # Poll for the user for 5 minutes
            attempts = (5 * 60) if poll_for_user_creation else 1
            for _ in range(attempts):
                attempts -= 1

                try:
                    quicksight_user_list.append(
                        user_client.describe_user(
                            AwsAccountId=account_id,
                            Namespace='default',
                            # \/ This is the format of the user name created by DIT SSO \/
                            UserName=f'quicksight_federation/{user_sso_id}',
                        )['User']
                    )
                    break

                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        if attempts > 0:
                            gevent.sleep(1)
                        elif poll_for_user_creation:
                            logger.exception(
                                "Did not find user with sso id `%s` after 5 minutes",
                                user_sso_id,
                            )
                    else:
                        raise e

        sync_quicksight_users(
            data_client=data_client,
            user_client=user_client,
            account_id=account_id,
            quicksight_user_list=quicksight_user_list,
        )

    else:
        next_token = None
        while True:
            list_user_args = dict(AwsAccountId=account_id, Namespace='default')
            if next_token:
                list_user_args['NextToken'] = next_token

            list_users_response = user_client.list_users(**list_user_args)
            quicksight_user_list: List[Dict[str, str]] = list_users_response['UserList']
            next_token = list_users_response.get('NextToken')

            sync_quicksight_users(
                data_client=data_client,
                user_client=user_client,
                account_id=account_id,
                quicksight_user_list=quicksight_user_list,
            )

            if not next_token:
                break

    logger.info(
        'sync_quicksight_user_datasources(%s, poll_for_user_creation=%s) finished',
        user_sso_ids_to_update,
        poll_for_user_creation,
    )


def _check_tools_access(user):
    if (
        user.user_permissions.filter(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()
        and not user.profile.tools_access_role_arn
    ):
        create_tools_access_iam_role_task.delay(user.id)


def create_user_from_sso(
    sso_id,
    primary_email,
    other_emails,
    first_name,
    last_name,
    check_tools_access_if_user_exists,
):
    User = get_user_model()
    try:
        user = User.objects.get(profile__sso_id=sso_id)
    except User.DoesNotExist:
        user, _ = User.objects.get_or_create(
            email__in=other_emails,
            defaults={'email': primary_email, 'username': primary_email},
        )

        user.save()
        user.profile.sso_id = sso_id
        try:
            user.save()
        except IntegrityError:
            # A concurrent request may have overtaken this one and created a user
            user = User.objects.get(profile__sso_id=sso_id)

        _check_tools_access(user)
    else:
        if check_tools_access_if_user_exists:
            _check_tools_access(user)

    changed = False

    if user.username != primary_email:
        changed = True
        user.username = primary_email

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

    if changed:
        user.save()

    return user


def hawk_request(method, url, body):
    hawk_id = settings.ACTIVITY_STREAM_HAWK_CREDENTIALS_ID
    hawk_key = settings.ACTIVITY_STREAM_HAWK_CREDENTIALS_KEY

    if not hawk_id or not hawk_key:
        raise HawkException("Hawk id or key not configured")

    content_type = 'application/json'
    header = Sender(
        {'id': hawk_id, 'key': hawk_key, 'algorithm': 'sha256'},
        url,
        method,
        content=body,
        content_type=content_type,
    ).request_header

    response = requests.request(
        method,
        url,
        data=body,
        headers={'Authorization': header, 'Content-Type': content_type},
    )
    return response.status_code, response.content


@celery_app.task(autoretry_for=(redis.exceptions.LockError,))
def create_tools_access_iam_role_task(user_id):
    with cache.lock(
        "create_tools_access_iam_role_task", blocking_timeout=0, timeout=360,
    ):
        _do_create_tools_access_iam_role(user_id)


def _do_create_tools_access_iam_role(user_id):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.exception('User id %d does not exist', user_id)
    else:
        create_tools_access_iam_role(
            user.email,
            str(user.profile.sso_id),
            user.profile.home_directory_efs_access_point_id,
        )
        gevent.sleep(1)


@celery_app.task(autoretry_for=(redis.exceptions.LockError,))
def sync_activity_stream_sso_users():
    with cache.lock(
        "activity_stream_sync_last_published_lock", blocking_timeout=0, timeout=1800
    ):
        _do_sync_activity_stream_sso_users()


def _do_sync_activity_stream_sso_users():
    last_published = cache.get(
        'activity_stream_sync_last_published', datetime.datetime.utcfromtimestamp(0)
    )

    endpoint = f'{settings.ACTIVITY_STREAM_BASE_URL}/v3/activities/_search'
    ten_seconds_before_last_published = last_published - datetime.timedelta(seconds=10)

    query = {
        "size": 1000,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"object.type": "dit:StaffSSO:User"}},
                    {
                        "range": {
                            "published": {
                                "gte": f"{ten_seconds_before_last_published.strftime('%Y-%m-%dT%H:%M:%S')}"
                            }
                        }
                    },
                ]
            }
        },
        "sort": [{"published": "asc"}, {"id": "asc"}],
    }

    while True:
        try:
            logger.info('Calling activity stream with query %s', json.dumps(query))
            status_code, response = hawk_request('GET', endpoint, json.dumps(query),)
        except HawkException as e:
            logger.error('Failed to call activity stream with error %s', e)
            break

        if status_code != 200:
            raise Exception(f'Failed to fetch SSO users: {response}')

        response_json = json.loads(response)

        if 'failures' in response_json['_shards']:
            raise Exception(
                f"Failed to fetch SSO users: {json.dumps(response_json['_shards']['failures'])}"
            )

        records = response_json['hits']['hits']

        if not records:
            break

        logger.info('Fetched %d record(s) from activity stream', len(records))

        for record in records:
            obj = record['_source']['object']

            user_id = obj['dit:StaffSSO:User:userId']
            emails = obj['dit:emailAddress']
            primary_email = emails[0]

            try:
                create_user_from_sso(
                    user_id,
                    primary_email,
                    emails,
                    obj['dit:firstName'],
                    obj['dit:lastName'],
                    check_tools_access_if_user_exists=True,
                )
            except IntegrityError:
                logger.exception('Failed to create user record')

        last_published_str = records[-1]['_source']['published']
        last_published = datetime.datetime.strptime(
            last_published_str, '%Y-%m-%dT%H:%M:%S.%fZ'
        )
        # paginate to next batch of records
        query['search_after'] = records[-1]['sort']

    cache.set('activity_stream_sync_last_published', last_published)


def log_visualisation_view(visualisation_link, user, event_type):
    EventLog.objects.create(
        user=user,
        event_type=event_type,
        content_type=ContentType.objects.get_for_model(VisualisationLink),
        object_id=visualisation_link.id,
        extra={
            "name": visualisation_link.name,
            "visualisation_identifier": visualisation_link.identifier,
        },
    ).save()


def fetch_visualisation_log_events(log_group, log_stream):
    client = boto3.client('logs')
    events = []
    next_token = None
    while True:
        try:
            response = client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                **{'nextToken': next_token} if next_token else {},
            )
        except ClientError:
            return []
        next_token = response.get('nextForwardToken')
        events += response.get('events', [])
        if next_token is None or not response['events']:
            break
    return events
