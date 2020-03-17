''' Spawners control and report on application instances
'''

import datetime
import json
import logging
import os
import subprocess

import boto3
from botocore.exceptions import ClientError
import gevent

from dataworkspace.cel import celery_app
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.gitlab import (
    ECR_PROJECT_ID,
    SUCCESS_PIPELINE_STATUSES,
    RUNNING_PIPELINE_STATUSES,
    gitlab_api_v4,
    gitlab_api_v4_ecr_pipeline_trigger,
)
from dataworkspace.apps.core.utils import create_s3_role

logger = logging.getLogger('app')


def get_spawner(name):
    return {'PROCESS': ProcessSpawner, 'FARGATE': FargateSpawner}[name]


@celery_app.task()
def spawn(
    name,
    user_email_address,
    user_sso_id,
    tag,
    application_instance_id,
    spawner_options,
    db_credentials,
):
    get_spawner(name).spawn(
        user_email_address,
        user_sso_id,
        tag,
        application_instance_id,
        spawner_options,
        db_credentials,
    )


@celery_app.task()
def stop(name, application_instance_id):
    get_spawner(name).stop(application_instance_id)


class ProcessSpawner:
    ''' A slightly overcomplicated and slow local-process spawner, but it is
    designed to simulate multi-stage spawners that call remote APIs. Only
    safe when the cluster is of size 1, and only handles a single running
    process, which must listen on port 8888
    '''

    @staticmethod
    def spawn(_, __, ___, application_instance_id, spawner_options, db_credentials):

        try:
            gevent.sleep(1)
            cmd = json.loads(spawner_options)['CMD']

            database_env = {
                f'DATABASE_DSN__{database["memorable_name"]}': f'host={database["db_host"]} '
                f'port={database["db_port"]} sslmode=require dbname={database["db_name"]} '
                f'user={database["db_user"]} password={database["db_password"]}'
                for database in db_credentials
            }

            logger.info('Starting %s', cmd)
            proc = subprocess.Popen(cmd, cwd='/home/django', env=database_env)

            application_instance = ApplicationInstance.objects.get(
                id=application_instance_id
            )
            application_instance.spawner_application_instance_id = json.dumps(
                {'process_id': proc.pid}
            )
            application_instance.save(update_fields=['spawner_application_instance_id'])

            gevent.sleep(1)
            application_instance.proxy_url = 'http://localhost:8888/'
            application_instance.save(update_fields=['proxy_url'])
        except Exception:
            logger.exception('PROCESS %s %s', application_instance_id, spawner_options)
            if proc:
                os.kill(int(proc.pid), 9)

    @staticmethod
    def state(_, created_date, spawner_application_id, proxy_url):
        ten_seconds_ago = datetime.datetime.now() + datetime.timedelta(seconds=-10)
        twenty_seconds_ago = datetime.datetime.now() + datetime.timedelta(seconds=-20)
        spawner_application_id_parsed = json.loads(spawner_application_id)

        # We have 10 seconds for the spawner to create the ID. In this case,
        # it's creating the process ID, which should happen almost immediately
        # If it doesn't, the instance may have died.

        def process_status():
            process_id = spawner_application_id_parsed['process_id']
            os.kill(process_id, 0)
            return 'RUNNING'

        try:
            return (
                'RUNNING'
                if not spawner_application_id_parsed and ten_seconds_ago < created_date
                else 'STOPPED'
                if not spawner_application_id_parsed
                else 'RUNNING'
                if not proxy_url and twenty_seconds_ago < created_date
                else 'STOPPED'
                if not proxy_url
                else process_status()
            )

        except Exception:
            logger.exception('PROCESS %s %s', spawner_application_id_parsed, proxy_url)
            return 'STOPPED'

    @staticmethod
    def stop(application_instance_id):
        application_instance = ApplicationInstance.objects.get(
            id=application_instance_id
        )
        spawner_application_id = application_instance.spawner_application_instance_id
        spawner_application_id_parsed = json.loads(spawner_application_id)
        try:
            os.kill(int(spawner_application_id_parsed['process_id']), 9)
        except ProcessLookupError:
            pass


class FargateSpawner:
    ''' Spawning is not HA: if the current server goes down after the
    ApplicationInstance is called, but before the ECS task is created, and has
    an IP address, from the point of view of the client, spawning won't
    continue and it will eventually be show to the client as an error.

    However,

    - An error would be shown in case of other error as well
    - A refresh of the browser page would spawn a new task
    - The planned reaper of idle tasks would eventually stop the unused task.

    So for now, this is acceptable.
    '''

    @staticmethod
    def spawn(
        user_email_address,
        user_sso_id,
        tag,
        application_instance_id,
        spawner_options,
        db_credentials,
    ):

        try:
            task_arn = None
            options = json.loads(spawner_options)

            cluster_name = options['CLUSTER_NAME']
            container_name = options['CONTAINER_NAME']
            definition_arn = options['DEFINITION_ARN']
            ecr_repository_name = options.get('ECR_REPOSITORY_NAME')
            security_groups = options['SECURITY_GROUPS']
            subnets = options['SUBNETS']
            cmd = options['CMD'] if 'CMD' in options else []
            env = options.get('ENV', {})
            port = options['PORT']
            s3_sync = options['S3_SYNC'] == 'true'

            s3_region = options['S3_REGION']
            s3_host = options['S3_HOST']
            s3_bucket = options['S3_BUCKET']

            database_env = {
                f'DATABASE_DSN__{database["memorable_name"]}': f'host={database["db_host"]} '
                f'port={database["db_port"]} sslmode=require dbname={database["db_name"]} '
                f'user={database["db_user"]} password={database["db_password"]}'
                for database in db_credentials
            }

            logger.info('Starting %s', cmd)

            role_arn, s3_prefix = create_s3_role(user_email_address, user_sso_id)

            s3_env = {
                'S3_PREFIX': s3_prefix,
                'S3_REGION': s3_region,
                'S3_HOST': s3_host,
                'S3_BUCKET': s3_bucket,
            }

            application_instance = ApplicationInstance.objects.get(
                id=application_instance_id
            )

            # Build tag if we can and it doesn't already exist
            if (
                ecr_repository_name
                and tag
                and application_instance.commit_id
                and application_instance.application_template.gitlab_project_id
                and not _ecr_tag_exists(ecr_repository_name, tag)
            ):
                pipeline = gitlab_api_v4_ecr_pipeline_trigger(
                    ECR_PROJECT_ID,
                    application_instance.application_template.gitlab_project_id,
                    application_instance.commit_id,
                    ecr_repository_name,
                    tag,
                )
                if 'id' not in pipeline:
                    raise Exception('Unable to start pipeline: {}'.format(pipeline))
                pipeline_id = pipeline['id']

                for _ in range(0, 60 * 5):
                    gevent.sleep(3)
                    pipeline = _gitlab_ecr_pipeline_get(pipeline_id)
                    logger.info('Fetched pipeline %s', pipeline)
                    if (
                        pipeline['status'] not in RUNNING_PIPELINE_STATUSES
                        and pipeline['status'] not in SUCCESS_PIPELINE_STATUSES
                    ):
                        raise Exception('Pipeline failed {}'.format(pipeline))
                    if pipeline['status'] in SUCCESS_PIPELINE_STATUSES:
                        break
                else:
                    logger.error('Pipeline took too long, cancelling: %s', pipeline)
                    _gitlab_ecr_pipeline_cancel(pipeline_id)
                    raise Exception('Pipeline {} took too long'.format(pipeline))

            # Tag is given, create a new task definition
            definition_arn_with_image = (
                _fargate_task_definition_with_tag(definition_arn, container_name, tag)
                if tag
                else definition_arn
            )

            # If memory or cpu are given, create a new task definition.
            cpu = application_instance.cpu
            memory = application_instance.memory
            cpu_or_mem = cpu is not None or memory is not None
            definition_arn_with_cpu_memory_image = (
                _fargate_task_definition_with_cpu_memory(
                    definition_arn_with_image, cpu, memory
                )
                if cpu_or_mem
                else definition_arn_with_image
            )

            for i in range(0, 10):
                # Sometimes there is an error assuming the new role: both IAM  and ECS are
                # eventually consistent
                try:
                    start_task_response = _fargate_task_run(
                        role_arn,
                        cluster_name,
                        container_name,
                        definition_arn_with_cpu_memory_image,
                        security_groups,
                        subnets,
                        cmd,
                        {**s3_env, **database_env, **env},
                        s3_sync,
                    )
                except ClientError:
                    gevent.sleep(3)
                    if i == 9:
                        raise
                else:
                    break

            task = (
                start_task_response['tasks'][0]
                if 'tasks' in start_task_response
                else start_task_response['task']
            )
            task_arn = task['taskArn']
            application_instance.spawner_application_instance_id = json.dumps(
                {'task_arn': task_arn}
            )
            application_instance.spawner_created_at = task['createdAt']
            application_instance.spawner_cpu = task['cpu']
            application_instance.spawner_memory = task['memory']
            application_instance.save(
                update_fields=[
                    'spawner_application_instance_id',
                    'spawner_created_at',
                    'spawner_cpu',
                    'spawner_memory',
                ]
            )

            application_instance.refresh_from_db()
            if application_instance.state == 'STOPPED':
                raise Exception('Application set to stopped before spawning complete')

            for _ in range(0, 60):
                ip_address = _fargate_task_ip(options['CLUSTER_NAME'], task_arn)
                if ip_address:
                    application_instance.proxy_url = f'http://{ip_address}:{port}'
                    application_instance.save(update_fields=['proxy_url'])
                    return
                gevent.sleep(3)

            raise Exception('Spawner timed out before finding ip address')
        except Exception:
            logger.exception('FARGATE %s %s', application_instance_id, spawner_options)
            if task_arn:
                _fargate_task_stop(cluster_name, task_arn)

    @staticmethod
    def state(spawner_options, created_date, spawner_application_id, proxy_url):
        logger.info(spawner_options)
        spawner_options = json.loads(spawner_options)
        spawner_application_id_parsed = json.loads(spawner_application_id)
        cluster_name = spawner_options['CLUSTER_NAME']

        three_minutes_ago = datetime.datetime.now() + datetime.timedelta(seconds=-180)
        twenty_seconds_ago = datetime.datetime.now() + datetime.timedelta(seconds=-20)

        # We can't just depend on connectivity to the proxy url, since another
        # task may now be using is IP address. We must query the ECS API
        def get_task_status():
            task_arn = spawner_application_id_parsed['task_arn']
            # Newly created tasks may not yet report a status, or may report
            # status inconsistently due to eventual consistency
            status = _fargate_task_status(cluster_name, task_arn)
            return (
                'RUNNING'
                if status is None and three_minutes_ago < created_date
                else 'STOPPED'
                if status is None
                else status
            )

        try:
            return (
                'RUNNING'
                if not spawner_application_id_parsed
                and twenty_seconds_ago < created_date
                else 'STOPPED'
                if not spawner_application_id_parsed
                else 'RUNNING'
                if not proxy_url and three_minutes_ago < created_date
                else 'STOPPED'
                if not proxy_url
                else get_task_status()
            )
        except Exception:
            logger.exception('FARGATE %s %s', spawner_application_id_parsed, proxy_url)
            return 'STOPPED'

    @staticmethod
    def stop(application_instance_id):
        application_instance = ApplicationInstance.objects.get(
            id=application_instance_id
        )
        options = json.loads(application_instance.spawner_application_template_options)
        cluster_name = options['CLUSTER_NAME']
        task_arn = json.loads(application_instance.spawner_application_instance_id)[
            'task_arn'
        ]
        _fargate_task_stop(cluster_name, task_arn)

        sleep_time = 1
        for _ in range(0, 8):
            try:
                task = _fargate_task_describe(cluster_name, task_arn)
                if 'stoppedAt' in task:
                    application_instance.spawner_stopped_at = task['stoppedAt']
                    application_instance.save(update_fields=['spawner_stopped_at'])
                    break
            except Exception:
                pass
            gevent.sleep(sleep_time)
            sleep_time = sleep_time * 2


def _gitlab_ecr_pipeline_cancel(pipeline_id):
    return gitlab_api_v4(
        'POST', f'/projects/{ECR_PROJECT_ID}/pipelines/{pipeline_id}/cancel'
    )


def _gitlab_ecr_pipeline_get(pipeline_id):
    return gitlab_api_v4('GET', f'/projects/{ECR_PROJECT_ID}/pipelines/{pipeline_id}')


def _ecr_tag_exists(repositoryName, tag):
    client = boto3.client('ecr')
    try:
        return bool(
            client.describe_images(
                repositoryName=repositoryName, imageIds=[{'imageTag': tag}]
            )['imageDetails']
        )
    except client.exceptions.ImageNotFoundException:
        return False


def _fargate_task_definition_with_tag(task_family, container_name, tag):
    client = boto3.client('ecs')
    describe_task_response = client.describe_task_definition(taskDefinition=task_family)
    container = [
        container
        for container in describe_task_response['taskDefinition'][
            'containerDefinitions'
        ]
        if container['name'] == container_name
    ][0]
    container['image'] += ':' + tag
    describe_task_response['taskDefinition']['family'] = task_family + '-' + tag

    register_tag_response = client.register_task_definition(
        **{
            key: value
            for key, value in describe_task_response['taskDefinition'].items()
            if key
            in [
                'family',
                'taskRoleArn',
                'executionRoleArn',
                'networkMode',
                'containerDefinitions',
                'volumes',
                'placementConstraints',
                'requiresCompatibilities',
                'cpu',
                'memory',
            ]
        }
    )
    return register_tag_response['taskDefinition']['taskDefinitionArn']


def _fargate_task_definition_with_cpu_memory(task_family, cpu, memory):
    client = boto3.client('ecs')
    describe_task_response = client.describe_task_definition(taskDefinition=task_family)
    if cpu is not None:
        describe_task_response['taskDefinition']['cpu'] = cpu
    if memory is not None:
        describe_task_response['taskDefinition']['memory'] = memory
    describe_task_response['taskDefinition']['family'] = (
        task_family
        + (f'-{cpu}' if cpu is not None else '')
        + (f'-{memory}' if memory is not None else '')
    )

    register_tag_response = client.register_task_definition(
        **{
            key: value
            for key, value in describe_task_response['taskDefinition'].items()
            if key
            in [
                'family',
                'taskRoleArn',
                'executionRoleArn',
                'networkMode',
                'containerDefinitions',
                'volumes',
                'placementConstraints',
                'requiresCompatibilities',
                'cpu',
                'memory',
            ]
        }
    )
    return register_tag_response['taskDefinition']['taskDefinitionArn']


def _fargate_task_ip(cluster_name, arn):
    described_task = _fargate_task_describe(cluster_name, arn)

    ip_address_attachements = (
        [
            attachment['value']
            for attachment in described_task['attachments'][0]['details']
            if attachment['name'] == 'privateIPv4Address'
        ]
        if described_task
        and 'attachments' in described_task
        and described_task['attachments']
        else []
    )
    ip_address = ip_address_attachements[0] if ip_address_attachements else ''

    return ip_address


def _fargate_task_status(cluster_name, arn):
    described_task = _fargate_task_describe(cluster_name, arn)
    logger.info('Described task %s %s %s', cluster_name, arn, described_task)

    # Simplify the status. We just care if it's running or will be running
    # Creation of task is eventually consistent, so we don't have a good way
    # of differentiating between a task just created, or long destroyed
    return (
        None
        if not described_task
        else 'RUNNING'
        if described_task['lastStatus'] in ('PROVISIONING', 'PENDING', 'RUNNING')
        else 'STOPPED'
    )


def _fargate_task_describe(cluster_name, arn):
    client = boto3.client('ecs')

    described_tasks = client.describe_tasks(cluster=cluster_name, tasks=[arn])

    task = (
        described_tasks['tasks'][0]
        if 'tasks' in described_tasks and described_tasks['tasks']
        else described_tasks['task']
        if 'task' in described_tasks
        else None
    )

    return task


def _fargate_task_stop(cluster_name, task_arn):
    client = boto3.client('ecs')
    sleep_time = 1
    for _ in range(0, 6):
        try:
            client.stop_task(cluster=cluster_name, task=task_arn)
        except Exception:
            gevent.sleep(sleep_time)
            sleep_time = sleep_time * 2
        else:
            return
    raise Exception('Unable to stop Fargate task {}'.format(task_arn))


def _fargate_task_run(
    role_arn,
    cluster_name,
    container_name,
    definition_arn,
    security_groups,
    subnets,
    command_and_args,
    env,
    s3_sync,
):
    client = boto3.client('ecs')

    return client.run_task(
        cluster=cluster_name,
        taskDefinition=definition_arn,
        overrides={
            'taskRoleArn': role_arn,
            'containerOverrides': [
                {
                    **({'command': command_and_args} if command_and_args else {}),
                    'environment': [
                        {'name': name, 'value': value} for name, value in env.items()
                    ],
                    'name': container_name,
                }
            ]
            + (
                [
                    {
                        'name': 's3sync',
                        'environment': [
                            {'name': name, 'value': value}
                            for name, value in env.items()
                        ],
                    }
                ]
                if s3_sync
                else []
            ),
        },
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'assignPublicIp': 'DISABLED',
                'securityGroups': security_groups,
                'subnets': subnets,
            }
        },
    )
