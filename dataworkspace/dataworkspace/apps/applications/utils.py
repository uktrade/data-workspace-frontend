import datetime
import hashlib
import json
import logging
import urllib.parse

import gevent
import requests
from psycopg2 import connect, sql

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from django_db_geventpool.utils import close_connection

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
from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.applications.gitlab import gitlab_has_developer_access
from dataworkspace.cel import celery_app

logger = logging.getLogger('app')


class MetricsException(Exception):
    pass


class ExpectedMetricsException(MetricsException):
    pass


class UnexpectedMetricsException(MetricsException):
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
        # Redundant, but making it explicit that host_basename is unchanged
        host_basename = host_basename
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

    sso_id_hex = hashlib.sha256(
        str(application_instance.owner.profile.sso_id).encode('utf-8')
    ).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    return {
        'proxy_url': application_instance.proxy_url,
        'state': api_state,
        'user': sso_id_hex_short,
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
    (
        application_template,
        _,
        host_user,
        commit_id,
    ) = application_template_tag_user_commit_from_host(public_host)

    request_sso_id_hex = hashlib.sha256(
        str(request.user.profile.sso_id).encode('utf-8')
    ).hexdigest()

    is_preview = commit_id is not None

    def is_tool_and_correct_user_and_allowed_to_start():
        return (
            application_template.application_type == 'TOOL'
            and host_user == request_sso_id_hex[:8]
            and request.user.has_perm('applications.start_all_applications')
        )

    def is_published_visualisation_and_requires_authentication():
        return (
            not is_preview
            and application_template.visible is True
            and application_template.application_type == 'VISUALISATION'
            and application_template.user_access_type == 'REQUIRES_AUTHENTICATION'
        )

    def is_published_visualisation_and_requires_authorisation_and_has_authorisation():
        return (
            not is_preview
            and application_template.visible is True
            and application_template.application_type == 'VISUALISATION'
            and application_template.user_access_type == 'REQUIRES_AUTHORIZATION'
            and request.user.applicationtemplateuserpermission_set.filter(
                application_template=application_template
            ).exists()
        )

    def is_visualisation_preview_and_has_gitlab_developer():
        return (
            is_preview
            and application_template.application_type == 'VISUALISATION'
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
        raise ExpectedMetricsException(f'Unknown')

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
        except Exception:
            logger.exception(
                'kill_idle_fargate: Unable to find CPU usage for %s', instance
            )
            continue

        logger.info('kill_idle_fargate: CPU usage for %s is %s', instance, max_cpu)

        if max_cpu >= 1.0:
            continue

        try:
            stop_spawner_and_application(instance)
        except Exception:
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
            except Exception:
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
    logger.info('delete_unused_datasets_users: Start')

    for memorable_name, database_data in settings.DATABASES_DATA.items():
        database_obj = Database.objects.get(memorable_name=memorable_name)
        database_name = database_data['NAME']

        with connect(database_dsn(database_data)) as conn, conn.cursor() as cur:
            logger.info('delete_unused_datasets_users: finding database users')
            cur.execute(
                """
                SELECT usename FROM pg_catalog.pg_user
                WHERE valuntil != 'infinity' AND usename LIKE 'user_%'
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
                        with cache.lock(f'database-grant-connect-{database_name}'):
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
                            with cache.lock(
                                f'database-grant--{database_name}--{schema}'
                            ):
                                for schema_revoke in schema_revokes:
                                    try:
                                        cur.execute(
                                            sql.SQL(schema_revoke).format(
                                                sql.Identifier(schema),
                                                sql.Identifier(usename),
                                            )
                                        )
                                    except Exception:
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
                    except Exception:
                        logger.exception(
                            'delete_unused_datasets_users: Failed deleting %s', usename
                        )
                    else:
                        logger.info(
                            'delete_unused_datasets_users: revoked credentials for and dropped %s',
                            usename,
                        )

    logger.info('delete_unused_datasets_users: End')
