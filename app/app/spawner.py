''' Spawners control and report on application instances
'''

import base64
import datetime
import hashlib
import os
import json
import logging
import subprocess

import boto3
import gevent

from app.cel import (
    celery_app,
)
from app.models import (
    ApplicationInstance,
)


logger = logging.getLogger('app')


def get_spawner(name):
    return {
        'PROCESS': ProcessSpawner,
        'FARGATE': FargateSpawner,
    }[name]


@celery_app.task()
def spawn(name, user_email_address, user_sso_id, application_instance_id, spawner_options, db_credentials):
    get_spawner(name).spawn(user_email_address, user_sso_id, application_instance_id, spawner_options, db_credentials)


class ProcessSpawner():
    ''' A slightly overcomplicated and slow local-process spawner, but it is
    designed to simulate multi-stage spawners that call remote APIs. Only
    safe when the cluster is of size 1, and only handles a single running
    process, which must listen on port 8888
    '''

    @staticmethod
    def spawn(_, __, application_instance_id, spawner_options, ___):

        def _spawn():
            try:
                gevent.sleep(1)
                cmd = json.loads(spawner_options)['CMD']
                logger.info('Starting %s', cmd)
                proc = subprocess.Popen(cmd, cwd='/home/django')

                application_instance = ApplicationInstance.objects.get(
                    id=application_instance_id,
                )
                application_instance.spawner_application_instance_id = json.dumps({
                    'process_id': proc.pid,
                })
                application_instance.save()

                gevent.sleep(1)
                application_instance.proxy_url = 'http://localhost:8888/'
                application_instance.save()
            except Exception:
                logger.exception('PROCESS %s %s', application_instance_id, spawner_options)
                if proc:
                    os.kill(int(proc.pid), 9)

        gevent.spawn(_spawn)

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
            return \
                'RUNNING' if not spawner_application_id_parsed and ten_seconds_ago < created_date else \
                'STOPPED' if not spawner_application_id_parsed else \
                'RUNNING' if not proxy_url and twenty_seconds_ago < created_date else \
                'STOPPED' if not proxy_url else \
                process_status()

        except Exception:
            logger.exception('PROCESS %s %s', spawner_application_id_parsed, proxy_url)
            return 'STOPPED'

    @staticmethod
    def can_stop(_, __):
        return True

    @staticmethod
    def stop(_, spawner_application_id):
        spawner_application_id_parsed = json.loads(spawner_application_id)
        try:
            os.kill(int(spawner_application_id_parsed['process_id']), 9)
        except ProcessLookupError:
            pass


class FargateSpawner():
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
    def spawn(user_email_address, user_sso_id, application_instance_id, spawner_options, db_credentials):

        def _spawn():
            try:
                task_arn = None
                options = json.loads(spawner_options)

                role_prefix = options['ROLE_PREFIX']
                cluster_name = options['CLUSTER_NAME']
                container_name = options['CONTAINER_NAME']
                definition_arn = options['DEFINITION_ARN']
                security_groups = options['SECURITY_GROUPS']
                subnets = options['SUBNETS']
                cmd = options['CMD'] if 'CMD' in options else []
                env = options['ENV']
                port = options['PORT']
                assume_role_policy_document = base64.b64decode(
                    options['ASSUME_ROLE_POLICY_DOCUMENT_BASE64']).decode('utf-8')
                policy_name = options['POLICY_NAME']
                policy_document_template = base64.b64decode(
                    options['POLICY_DOCUMENT_TEMPLATE_BASE64']).decode('utf-8')
                permissions_boundary_arn = options['PERMISSIONS_BOUNDARY_ARN']

                s3_region = options['S3_REGION']
                s3_host = options['S3_HOST']
                s3_bucket = options['S3_BUCKET']

                database_env = {
                    f'DATABASE_DSN__{database["memorable_name"]}':
                    f'host={database["db_host"]} port={database["db_port"]} sslmode=require dbname={database["db_name"]} user={database["db_user"]} password={database["db_password"]}'
                    for database in db_credentials
                }

                logger.info('Starting %s', cmd)

                # Create a role
                iam_client = boto3.client('iam')

                role_name = role_prefix + user_email_address
                s3_prefix = 'user/federated/' + \
                    hashlib.sha256(user_sso_id.encode('utf-8')).hexdigest() + '/'

                try:
                    iam_client.create_role(
                        RoleName=role_name,
                        Path='/',
                        AssumeRolePolicyDocument=assume_role_policy_document,
                        PermissionsBoundary=permissions_boundary_arn,
                    )
                except iam_client.exceptions.EntityAlreadyExistsException:
                    pass
                else:
                    gevent.sleep(10)

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=policy_document_template.replace('__S3_PREFIX__', s3_prefix)
                )

                gevent.sleep(3)

                role_arn = iam_client.get_role(
                    RoleName=role_name
                )['Role']['Arn']
                logger.info('User (%s) set up AWS role... done (%s)', user_email_address, role_arn)

                s3_env = {
                    'S3_PREFIX': s3_prefix,
                    'S3_REGION': s3_region,
                    'S3_HOST': s3_host,
                    'S3_BUCKET': s3_bucket,
                }

                start_task_response = _fargate_task_run(
                    role_arn, cluster_name, container_name, definition_arn, security_groups, subnets,
                    cmd, {**s3_env, **database_env, **env},
                )

                task_arn = \
                    start_task_response['tasks'][0]['taskArn'] if 'tasks' in start_task_response else \
                    start_task_response['task']['taskArn']
                application_instance = ApplicationInstance.objects.get(
                    id=application_instance_id,
                )
                application_instance.spawner_application_instance_id = json.dumps({
                    'task_arn': task_arn,
                })
                application_instance.save()

                for _ in range(0, 60):
                    ip_address = _fargate_task_ip(options['CLUSTER_NAME'], task_arn)
                    if ip_address:
                        application_instance.proxy_url = f'http://{ip_address}:{port}'
                        application_instance.save()
                        return
                    gevent.sleep(3)

                raise Exception('Spawner timed out before finding ip address')
            except Exception:
                logger.exception('FARGATE %s %s', application_instance_id, spawner_options)
                if task_arn:
                    _fargate_task_stop(cluster_name, task_arn)

        gevent.spawn(_spawn)

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
            return \
                'RUNNING' if status is None and three_minutes_ago < created_date else \
                'STOPPED' if status is None else \
                status

        try:
            return \
                'RUNNING' if not spawner_application_id_parsed and twenty_seconds_ago < created_date else \
                'STOPPED' if not spawner_application_id_parsed else \
                'RUNNING' if not proxy_url and three_minutes_ago < created_date else \
                'STOPPED' if not proxy_url else \
                get_task_status()
        except Exception:
            logger.exception('FARGATE %s %s', spawner_application_id_parsed, proxy_url)
            return 'STOPPED'

    @staticmethod
    def can_stop(_, spawner_application_id):
        return 'task_arn' in json.loads(spawner_application_id)

    @staticmethod
    def stop(spawner_options, spawner_application_id):
        options = json.loads(spawner_options)
        cluster_name = options['CLUSTER_NAME']
        task_arn = json.loads(spawner_application_id)['task_arn']
        _fargate_task_stop(cluster_name, task_arn)


def _fargate_task_ip(cluster_name, arn):
    described_task = _fargate_task_describe(cluster_name, arn)

    ip_address_attachements = [
        attachment['value']
        for attachment in described_task['attachments'][0]['details']
        if attachment['name'] == 'privateIPv4Address'
    ] if described_task and 'attachments' in described_task and described_task['attachments'] else []
    ip_address = ip_address_attachements[0] if ip_address_attachements else ''

    return ip_address


def _fargate_task_status(cluster_name, arn):
    described_task = _fargate_task_describe(cluster_name, arn)
    logger.info('Described task %s %s %s', cluster_name, arn, described_task)

    # Simplify the status. We just care if it's running or will be running
    # Creation of task is eventually consistent, so we don't have a good way
    # of differentiating between a task just created, or long destroyed
    return \
        None if not described_task else \
        'RUNNING' if described_task['lastStatus'] in ('PROVISIONING', 'PENDING', 'RUNNING') else \
        'STOPPED'


def _fargate_task_describe(cluster_name, arn):
    client = boto3.client('ecs')

    described_tasks = client.describe_tasks(
        cluster=cluster_name,
        tasks=[arn],
    )

    task = \
        described_tasks['tasks'][0] if 'tasks' in described_tasks and described_tasks['tasks'] else \
        described_tasks['task'] if 'task' in described_tasks else \
        None

    return task


def _fargate_task_stop(cluster_name, task_arn):
    client = boto3.client('ecs')
    client.stop_task(
        cluster=cluster_name,
        task=task_arn,
    )


def _fargate_task_run(role_arn, cluster_name, container_name, definition_arn,
                      security_groups, subnets, command_and_args, env):
    client = boto3.client('ecs')

    return client.run_task(
        cluster=cluster_name,
        taskDefinition=definition_arn,
        overrides={
            'taskRoleArn': role_arn,
            'containerOverrides': [{
                **(
                    {
                        'command': command_and_args,
                    } if command_and_args else {}
                ),
                'environment': [
                    {
                        'name': name,
                        'value': value,
                    } for name, value in env.items()
                ],
                'name': container_name,
            }],
        },
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'assignPublicIp': 'DISABLED',
                'securityGroups': security_groups,
                'subnets': subnets,
            },
        },
    )
