import datetime
import hashlib
import logging
import requests
import urllib.parse


from django.conf import settings

from dataworkspace.apps.applications.spawner import get_spawner
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.cel import celery_app

logger = logging.getLogger('app')


def api_application_dict(application_instance):
    spawner_state = get_spawner(application_instance.application_template.spawner).state(
        application_instance.spawner_application_template_options,
        application_instance.created_date.replace(tzinfo=None),
        application_instance.spawner_application_instance_id,
        application_instance.public_host,
    )

    # Only pass through the database state if the spawner is running,
    # Otherwise, we are in an error condition, and so return the spawner
    # state, so the client (i.e. the proxy) knows to take action
    api_state = \
        application_instance.state if spawner_state == 'RUNNING' else \
        spawner_state

    template_name = application_instance.application_template.name
    sso_id_hex = hashlib.sha256(str(application_instance.owner.profile.sso_id).encode('utf-8')).hexdigest()
    sso_id_hex_short = sso_id_hex[:8]

    return {
        'proxy_url': application_instance.proxy_url,
        'state': api_state,
        'user': sso_id_hex_short,
        'name': template_name,
    }


def get_api_visible_application_instance_by_public_host(public_host):
    # From the point of view of the API, /public_host/<host-name> is a single
    # spawning or running application, and if it's not spawning or running
    # it doesn't exist. 'STOPPING' an application is DELETEing it. This may
    # need to be changed in later versions for richer behaviour.
    return ApplicationInstance.objects.get(
        public_host=public_host, state__in=['RUNNING', 'SPAWNING'],
    )


def application_api_is_allowed(request, public_host):
    _, _, owner_sso_id_hex = public_host.partition('-')

    request_sso_id_hex = hashlib.sha256(
        str(request.user.profile.sso_id).encode('utf-8')).hexdigest()

    return (owner_sso_id_hex == request_sso_id_hex[:8] and
            request.user.has_perm('applications.start_all_applications'))


def stop_spawner_and_application(application_instance):
    get_spawner(application_instance.spawner).stop(
        application_instance.spawner_application_template_options,
        application_instance.spawner_application_instance_id,
    )
    set_application_stopped(application_instance)


def set_application_stopped(application_instance):
    application_instance.state = 'STOPPED'
    application_instance.single_running_or_spawning_integrity = str(application_instance.id)
    application_instance.save()


def application_instance_max_cpu(application_instance):
    # If we don't have the proxy url yet, we can't have any metrics yet.
    # This is expected and should not be shown as an error
    if application_instance.proxy_url is None:
        raise ValueError('Unknown')

    instance = urllib.parse.urlsplit(application_instance.proxy_url).hostname + ':8889'
    url = f'https://{settings.PROMETHEUS_DOMAIN}/api/v1/query'
    params = {
        'query': f'increase(precpu_stats__cpu_usage__total_usage{{instance="{instance}"}}[30s])[2h:30s]'
    }
    try:
        response = requests.get(url, params)
    except requests.RequestException:
        raise ValueError('Error connecting to metrics server')

    response_dict = response.json()
    if response_dict['status'] != 'success':
        raise ValueError(f'Metrics server return value is {response_dict["status"]}')

    try:
        values = response_dict['data']['result'][0]['values']
    except (IndexError, KeyError):
        # The server not having metrics yet should not be reported as an error
        raise ValueError(f'Unknown')

    max_cpu = 0.0
    ts_at_max = 0
    for ts, cpu in values:
        cpu_float = float(cpu) / (1000000000 * 30) * 100
        if cpu_float >= max_cpu:
            max_cpu = cpu_float
            ts_at_max = ts

    return max_cpu, ts_at_max


@celery_app.task()
def kill_idle_fargate():
    logger.info('kill_idle_fargate: Start')

    two_hours_ago = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=-2)
    instances = ApplicationInstance.objects.filter(
        spawner='FARGATE',
        state__in=['RUNNING', 'SPAWNING'],
        created_date__lt=two_hours_ago,
    )

    for instance in instances:
        if instance.state == 'SPAWNING':
            set_application_stopped(instance)
            continue

        logger.info('kill_idle_fargate: Attempting to find CPU usage of %s', instance)
        try:
            max_cpu, _ = application_instance_max_cpu(instance)
        except Exception:
            logger.exception('kill_idle_fargate: Unable to find CPU usage for %s', instance)
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
