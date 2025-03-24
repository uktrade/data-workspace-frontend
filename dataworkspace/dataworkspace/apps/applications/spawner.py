""" Spawners control and report on application instances
"""

import datetime
import json
import logging
import os
import re
import subprocess

import boto3
import gevent
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth import get_user_model

from dataworkspace.apps.applications.gitlab import (
    ECR_PROJECT_ID,
    RUNNING_PIPELINE_STATUSES,
    SUCCESS_PIPELINE_STATUSES,
    gitlab_api_v4,
    gitlab_api_v4_ecr_pipeline_trigger,
)
from dataworkspace.apps.applications.models import ApplicationInstance, ApplicationInstanceDbUsers
from dataworkspace.apps.arangodb.models import ApplicationInstanceArangoUsers
from dataworkspace.apps.arangodb.utils import new_private_arangodb_credentials
from dataworkspace.apps.core.models import Database
from dataworkspace.apps.core.utils import (
    USER_SCHEMA_STEM,
    clean_db_identifier,
    close_admin_db_connection_if_not_in_atomic_block,
    close_all_connections_if_not_in_atomic_block,
    create_tools_access_iam_role,
    db_role_schema_suffix_for_app,
    db_role_schema_suffix_for_user,
    generate_jwt_token,
    new_private_database_credentials,
    postgres_user,
    source_tables_for_app,
    source_tables_for_user,
    stable_identification_suffix,
    write_credentials_to_bucket,
)
from dataworkspace.cel import celery_app

logger = logging.getLogger("app")


def get_spawner(name):
    return {"PROCESS": ProcessSpawner, "FARGATE": FargateSpawner}[name]


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def spawn(
    name,
    user_id,
    tag,
    application_instance_id,
    spawner_options,
):
    user = get_user_model().objects.get(pk=user_id)
    application_instance = ApplicationInstance.objects.get(id=application_instance_id)

    (
        (
            source_tables_individual,
            (user_email_domain, source_tables_email_domain),
            source_tables_common,
        ),
        db_role_schema_suffix,
        db_user,
    ) = (
        (
            source_tables_for_user(user),
            db_role_schema_suffix_for_user(user),
            postgres_user(user.email),
        )
        if application_instance.application_template.application_type == "TOOL"
        else (
            source_tables_for_app(application_instance.application_template),
            db_role_schema_suffix_for_app(application_instance.application_template),
            postgres_user(application_instance.application_template.host_basename),
        )
    )

    credentials = new_private_database_credentials(
        db_role_schema_suffix,
        source_tables_individual,
        user_email_domain,
        source_tables_email_domain,
        source_tables_common,
        db_user,
        user if application_instance.application_template.application_type == "TOOL" else None,
        valid_for=datetime.timedelta(days=31),
    )

    arangodb_credentials = (
        new_private_arangodb_credentials(
            db_user,
            user,
        )
        if application_instance.application_template.application_type == "TOOL"
        else {}
    )

    mlflow_authorised_hosts, sub = (
        (
            list(
                user.authorised_mlflow_instances.all().values_list("instance__hostname", flat=True)
            ),
            user.email,
        )
        if application_instance.application_template.application_type == "TOOL"
        else (
            list(
                application_instance.application_template.authorised_mlflow_instances.all().values_list(
                    "mlflow_instance__hostname", flat=True
                )
            ),
            application_instance.application_template.host_basename,
        )
    )

    jwt_token = generate_jwt_token(mlflow_authorised_hosts, sub)

    if application_instance.application_template.application_type == "TOOL":
        # For AppStream to access credentials
        write_credentials_to_bucket(user, credentials)

    app_schema = f"{USER_SCHEMA_STEM}{db_role_schema_suffix}"

    get_spawner(name).spawn(
        user,
        tag,
        application_instance,
        spawner_options,
        credentials,
        jwt_token,
        mlflow_authorised_hosts,
        app_schema,
        arangodb_credentials,
    )


@celery_app.task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
@close_all_connections_if_not_in_atomic_block
def stop(name, application_instance_id):
    get_spawner(name).stop(application_instance_id)


class ProcessSpawner:
    """A slightly overcomplicated and slow local-process spawner, but it is
    designed to simulate multi-stage spawners that call remote APIs. Only
    safe when the cluster is of size 1, and only handles a single running
    process, which must listen on port 8888
    """

    @staticmethod
    def spawn(
        _,
        __,
        application_instance,
        spawner_options,
        credentials,
        jwt_token,
        mlflow_authorised_hosts,
        ___,
        arangodb_credentials,
    ):
        try:
            # The database users are stored so when the database users are cleaned up,
            # we know _not_ to delete any users used by running or spawning apps
            for creds in credentials:
                ApplicationInstanceDbUsers.objects.create(
                    application_instance=application_instance,
                    db_id=Database.objects.get(memorable_name=creds["memorable_name"]).id,
                    db_username=creds["db_user"],
                    db_persistent_role=creds["db_persistent_role"],
                )

            close_admin_db_connection_if_not_in_atomic_block()
            gevent.sleep(1)
            cmd = json.loads(spawner_options)["CMD"]

            database_env = _creds_to_env_vars(credentials)

            logger.info("Starting %s", cmd)
            # pylint: disable=consider-using-with
            proc = subprocess.Popen(
                cmd, cwd="/home/django", env={**database_env, **arangodb_credentials}
            )

            application_instance.spawner_application_instance_id = json.dumps(
                {"process_id": proc.pid}
            )
            application_instance.save(update_fields=["spawner_application_instance_id"])
            close_admin_db_connection_if_not_in_atomic_block()

            gevent.sleep(1)
            application_instance.proxy_url = "http://localhost:8888/"
            application_instance.save(update_fields=["proxy_url"])
            close_admin_db_connection_if_not_in_atomic_block()
        except Exception:  # pylint: disable=broad-except
            logger.exception("PROCESS %s %s", application_instance.id, spawner_options)
            if proc:
                os.kill(int(proc.pid), 9)

    @staticmethod
    def state(_, created_date, spawner_application_id, proxy_url):
        ten_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=10)
        twenty_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=20)
        spawner_application_id_parsed = json.loads(spawner_application_id)

        # We have 10 seconds for the spawner to create the ID. In this case,
        # it's creating the process ID, which should happen almost immediately
        # If it doesn't, the instance may have died.

        def process_status():
            process_id = spawner_application_id_parsed["process_id"]
            os.kill(process_id, 0)
            return "RUNNING"

        try:
            return (
                "RUNNING"
                if not spawner_application_id_parsed and ten_seconds_ago < created_date
                else (
                    "STOPPED"
                    if not spawner_application_id_parsed
                    else (
                        "RUNNING"
                        if not proxy_url and twenty_seconds_ago < created_date
                        else "STOPPED" if not proxy_url else process_status()
                    )
                )
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception("PROCESS %s %s", spawner_application_id_parsed, proxy_url)
            return "STOPPED"

    @staticmethod
    def stop(application_instance_id):
        application_instance = ApplicationInstance.objects.get(id=application_instance_id)
        spawner_application_id = application_instance.spawner_application_instance_id
        spawner_application_id_parsed = json.loads(spawner_application_id)
        try:
            os.kill(int(spawner_application_id_parsed["process_id"]), 9)
        except ProcessLookupError:
            pass


class FargateSpawner:
    """Spawning is not HA: if the current server goes down after the
    ApplicationInstance is called, but before the ECS task is created, and has
    an IP address, from the point of view of the client, spawning won't
    continue and it will eventually be show to the client as an error.

    However,

    - An error would be shown in case of other error as well
    - A refresh of the browser page would spawn a new task
    - The planned reaper of idle tasks would eventually stop the unused task.

    So for now, this is acceptable.
    """

    @staticmethod
    def spawn(
        user,
        tag,
        application_instance,
        spawner_options,
        credentials,
        jwt_token,
        mlflow_authorised_hosts,
        app_schema,
        arangodb_credentials,
    ):
        try:
            pipeline_id = None
            task_arn = None
            options = json.loads(spawner_options)

            cluster_name = options["CLUSTER_NAME"]
            container_name = options["CONTAINER_NAME"]
            definition_arn = options["DEFINITION_ARN"]
            ecr_repository_name = options.get("ECR_REPOSITORY_NAME")
            security_groups = options["SECURITY_GROUPS"]
            subnets = options["SUBNETS"]
            cmd = options["CMD"] if "CMD" in options else []
            env = options.get("ENV", {})
            port = options["PORT"]
            s3_sync = options["S3_SYNC"] == "true"

            s3_region = options["S3_REGION"]
            s3_host = options["S3_HOST"]
            s3_bucket = options["S3_BUCKET"]

            platform_version = options.get("PLATFORM_VERSION", "1.3.0")

            # The database users are stored so when the database users are cleaned up,
            # we know _not_ to delete any users used by running or spawning apps
            for creds in credentials:
                ApplicationInstanceDbUsers.objects.create(
                    application_instance=application_instance,
                    db_id=Database.objects.get(memorable_name=creds["memorable_name"]).id,
                    db_username=creds["db_user"],
                    db_persistent_role=creds["db_persistent_role"],
                )

            if arangodb_credentials:
                ApplicationInstanceArangoUsers.objects.create(
                    application_instance=application_instance,
                    db_username=arangodb_credentials["ARANGO_USER"],
                )

            database_env = _creds_to_env_vars(credentials)

            schema_env = {"APP_SCHEMA": app_schema}

            arangodb_env = arangodb_credentials

            matchbox_env = {"MB__CLIENT__DEFAULT_WAREHOUSE": "postgresql://"}

            user_efs_access_point_id = (
                user.profile.home_directory_efs_access_point_id
                if application_instance.application_template.application_type == "TOOL"
                else None
            )

            logger.info("Starting %s", cmd)

            user_email = user.email

            if application_instance.application_template.application_type == "TOOL":
                role_arn, s3_prefixes = create_tools_access_iam_role(
                    user.id, user_email, user_efs_access_point_id
                )
                s3_env = {
                    "S3_PREFIX": s3_prefixes["home"],
                    "S3_REGION": s3_region,
                    "S3_HOST": s3_host,
                    "S3_BUCKET": s3_bucket,
                    **{
                        f"S3_PREFIX_TEAM_{clean_db_identifier(name).upper()}": prefix
                        for name, prefix in s3_prefixes.items()
                        if name != "home"
                    },
                }
            else:
                role_arn = None
                s3_env = {}

            close_admin_db_connection_if_not_in_atomic_block()

            mlflow_env = {}
            if mlflow_authorised_hosts:
                mlflow_env = {
                    "MLFLOW_TRACKING_TOKEN": jwt_token,
                    "MLFLOW_TRACKING_URI": f"{mlflow_authorised_hosts[0]}:{settings.MLFLOW_PORT}",
                }

            # Build tag if we can and it doesn't already exist
            if (
                ecr_repository_name
                and tag
                and application_instance.commit_id
                and application_instance.application_template.gitlab_project_id
                and not _ecr_tag_exists(ecr_repository_name, tag)
            ):
                gitlab_project_id = application_instance.application_template.gitlab_project_id
                commit_id = application_instance.commit_id
                close_admin_db_connection_if_not_in_atomic_block()

                pipeline = gitlab_api_v4_ecr_pipeline_trigger(
                    ECR_PROJECT_ID,
                    gitlab_project_id,
                    commit_id,
                    ecr_repository_name,
                    tag,
                )
                if "id" not in pipeline:
                    raise Exception("Unable to start pipeline: {}".format(pipeline))
                pipeline_id = pipeline["id"]
                application_instance.spawner_application_instance_id = json.dumps(
                    {"pipeline_id": pipeline_id, "task_arn": None}
                )
                application_instance.save(update_fields=["spawner_application_instance_id"])
                close_admin_db_connection_if_not_in_atomic_block()

                for _ in range(0, 900):
                    gevent.sleep(3)
                    pipeline = _gitlab_ecr_pipeline_get(pipeline_id)
                    logger.info("Fetched pipeline %s", pipeline)
                    if (
                        pipeline["status"] not in RUNNING_PIPELINE_STATUSES
                        and pipeline["status"] not in SUCCESS_PIPELINE_STATUSES
                    ):
                        raise Exception("Pipeline failed {}".format(pipeline))
                    if pipeline["status"] in SUCCESS_PIPELINE_STATUSES:
                        break
                else:
                    logger.error("Pipeline took too long, cancelling: %s", pipeline)
                    _gitlab_ecr_pipeline_cancel(pipeline_id)
                    raise Exception("Pipeline {} took too long".format(pipeline))

            # It doesn't really matter what the suffix is: it could even be a random
            # number, but we choose the short hashed version of the SSO ID to help debugging
            task_family_suffix = stable_identification_suffix(str(user.profile.sso_id), short=True)
            definition_arn_with_image = _fargate_new_task_definition(
                role_arn,
                definition_arn,
                container_name,
                tag,
                task_family_suffix,
                settings.EFS_ID,
                user_efs_access_point_id,
            )

            cpu = application_instance.cpu
            memory = application_instance.memory
            close_admin_db_connection_if_not_in_atomic_block()

            for i in range(0, 10):
                # Sometimes there is an error assuming the new role: both IAM  and ECS are
                # eventually consistent
                try:
                    start_task_response = _fargate_task_run(
                        role_arn,
                        cluster_name,
                        container_name,
                        definition_arn_with_image,
                        security_groups,
                        subnets,
                        cpu,
                        memory,
                        cmd,
                        {
                            **s3_env,
                            **database_env,
                            **schema_env,
                            **env,
                            **mlflow_env,
                            **arangodb_env,
                            **matchbox_env,
                        },
                        s3_sync,
                        platform_version,
                    )
                except ClientError:
                    gevent.sleep(3)
                    if i == 9:
                        raise
                else:
                    break

            task = (
                start_task_response["tasks"][0]
                if "tasks" in start_task_response
                else start_task_response["task"]
            )
            task_arn = task["taskArn"]
            application_instance.spawner_application_instance_id = json.dumps(
                {"pipeline_id": pipeline_id, "task_arn": task_arn}
            )
            application_instance.spawner_created_at = task["createdAt"]
            application_instance.spawner_cpu = task["cpu"]
            application_instance.spawner_memory = task["memory"]
            application_instance.save(
                update_fields=[
                    "spawner_application_instance_id",
                    "spawner_created_at",
                    "spawner_cpu",
                    "spawner_memory",
                ]
            )

            application_instance.refresh_from_db()
            if application_instance.state == "STOPPED":
                raise Exception("Application set to stopped before spawning complete")

            close_admin_db_connection_if_not_in_atomic_block()

            for _ in range(0, 60):
                ip_address = _fargate_task_ip(options["CLUSTER_NAME"], task_arn)
                if ip_address:
                    conflicting_instances = ApplicationInstance.objects.filter(
                        proxy_url__regex=r".*\b" + re.escape(ip_address) + r"\b.*", state="RUNNING"
                    )
                    for instance in conflicting_instances:
                        instance.state = "STOPPED"
                        instance.save(update_fields=["state"])
                        logger.exception("We have two tools on the same IP!")
                    application_instance.proxy_url = f"http://{ip_address}:{port}"
                    application_instance.save(update_fields=["proxy_url"])
                    return
                gevent.sleep(3)

            raise Exception("Spawner timed out before finding ip address")
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Spawning %s %s %s",
                pipeline_id,
                application_instance.id,
                spawner_options,
            )
            if task_arn:
                _fargate_task_stop(cluster_name, task_arn)
            if pipeline_id:
                _gitlab_ecr_pipeline_cancel(pipeline_id)

    @staticmethod
    def state(  # pylint: disable=too-many-return-statements
        spawner_options, created_date, spawner_application_id, proxy_url
    ):
        close_admin_db_connection_if_not_in_atomic_block()
        try:
            logger.info(spawner_options)
            spawner_options = json.loads(spawner_options)
            spawner_application_id_parsed = json.loads(spawner_application_id)
            cluster_name = spawner_options["CLUSTER_NAME"]

            now = datetime.datetime.now()
            thirty_minutes_ago = now - datetime.timedelta(minutes=30)
            five_minutes_ago = now - datetime.timedelta(minutes=5)
            eight_minutes_ago = now - datetime.timedelta(minutes=8)

            task_arn = spawner_application_id_parsed.get("task_arn")
            pipeline_id = spawner_application_id_parsed.get("pipeline_id")

            # ... if started pipeline, but not yet the task, give 15 minutes to complete...
            if pipeline_id and not task_arn:
                pipeline = _gitlab_ecr_pipeline_get(pipeline_id)
                pipeline_status = pipeline["status"]
                if (
                    pipeline_status in RUNNING_PIPELINE_STATUSES
                    and created_date > thirty_minutes_ago
                ):
                    return "RUNNING"
                if pipeline_status not in SUCCESS_PIPELINE_STATUSES:
                    return "STOPPED"

            # ... find when the task _should_ have been created
            if pipeline_id:
                task_should_be_created = datetime.datetime.strptime(
                    _gitlab_ecr_pipeline_get(pipeline_id)["finished_at"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                )
            else:
                task_should_be_created = created_date

            # ... give five minutes to create the task...
            if not task_arn:
                if task_should_be_created > five_minutes_ago:
                    return "RUNNING"
                logger.exception(
                    "Task not created within five minutes: %s %s",
                    spawner_application_id_parsed,
                    proxy_url,
                )
                return "STOPPED"

            # .... give eight minutes to get the task itself (to mitigate eventual consistency)...
            task = _fargate_task_describe(cluster_name, task_arn)
            if task is None and task_should_be_created > eight_minutes_ago:
                return "RUNNING"
            if task is None:
                logger.exception(
                    "Task not running within 8 minutes: %s %s",
                    spawner_application_id_parsed,
                    proxy_url,
                )
                return "STOPPED"

            # ... and the spawner is running if the task is running or starting...
            if task["lastStatus"] in ("PROVISIONING", "PENDING", "RUNNING"):
                return "RUNNING"

            # ... and the spawner is stopped not if it's not
            return "STOPPED"

        except ClientError as exception_obj:
            logger.exception("FARGATE %s %s", spawner_application_id_parsed, proxy_url)
            if exception_obj.response["Error"]["Code"] == "ThrottlingException":
                return "RUNNING"
            return "STOPPED"
        except Exception:  # pylint: disable=broad-except
            return "STOPPED"

    @staticmethod
    def stop(application_instance_id):
        application_instance = ApplicationInstance.objects.get(id=application_instance_id)
        options = json.loads(application_instance.spawner_application_template_options)
        cluster_name = options["CLUSTER_NAME"]
        # If there is no task arn for the application mark it as stopped
        try:
            task_arn = json.loads(application_instance.spawner_application_instance_id)["task_arn"]
        except KeyError:
            if application_instance.state != "STOPPED":
                application_instance.state = "STOPPED"
                application_instance.single_running_or_spawning_integrity = str(
                    application_instance.id
                )
                application_instance.save(
                    update_fields=["state", "single_running_or_spawning_integrity"]
                )
            return

        _fargate_task_stop(cluster_name, task_arn)

        sleep_time = 1
        for _ in range(0, 8):
            try:
                task = _fargate_task_describe(cluster_name, task_arn)
                if "stoppedAt" in task:
                    application_instance.spawner_stopped_at = task["stoppedAt"]
                    application_instance.save(update_fields=["spawner_stopped_at"])
                    break
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to describe fargate task when stopping tool")
            gevent.sleep(sleep_time)
            sleep_time = sleep_time * 2

    @staticmethod
    def tags_for_tag(spawner_options, tag):
        return _ecr_tags_for_tag(spawner_options["ECR_REPOSITORY_NAME"], tag)

    @staticmethod
    def retag(spawner_options, existing_tag, new_tag):
        return _ecr_retag(spawner_options["ECR_REPOSITORY_NAME"], existing_tag, new_tag)


def _creds_to_env_vars(credentials):
    return dict(
        list(
            {
                f'DATABASE_DSN__{database["memorable_name"]}': f'host={database["db_host"]} '
                f'port={database["db_port"]} sslmode=require dbname={database["db_name"]} '
                f'user={database["db_user"]} password={database["db_password"]}'
                for database in credentials
            }.items()
        )
        + (
            list(
                {
                    # libpq-based libraries use these environment variables automatically
                    "PGHOST": credentials[0]["db_host"],
                    "PGPORT": credentials[0]["db_port"],
                    "PGSSLMODE": "require",
                    "PGDATABASE": credentials[0]["db_name"],
                    "PGUSER": credentials[0]["db_user"],
                    "PGPASSWORD": credentials[0]["db_password"],
                }.items()
            )
            if credentials
            else []
        )
    )


def _gitlab_ecr_pipeline_cancel(pipeline_id):
    return gitlab_api_v4("POST", f"/projects/{ECR_PROJECT_ID}/pipelines/{pipeline_id}/cancel")


def _gitlab_ecr_pipeline_get(pipeline_id):
    return gitlab_api_v4("GET", f"/projects/{ECR_PROJECT_ID}/pipelines/{pipeline_id}")


def _ecr_tag_exists(repositoryName, tag):
    client = _ecr_client()
    try:
        return bool(
            client.describe_images(repositoryName=repositoryName, imageIds=[{"imageTag": tag}])[
                "imageDetails"
            ]
        )
    except client.exceptions.ImageNotFoundException:
        return False


def _ecr_tags_for_tag(repositoryName, tag):
    client = _ecr_client()
    try:
        return client.describe_images(repositoryName=repositoryName, imageIds=[{"imageTag": tag}])[
            "imageDetails"
        ][0]["imageTags"]
    except client.exceptions.ImageNotFoundException:
        return []


def _ecr_retag(repositoryName, existing_tag, new_tag):
    client = _ecr_client()

    manifest = client.batch_get_image(
        repositoryName=repositoryName, imageIds=[{"imageTag": existing_tag}]
    )["images"][0]["imageManifest"]

    try:
        client.put_image(repositoryName=repositoryName, imageTag=new_tag, imageManifest=manifest)
    except client.exceptions.ImageAlreadyExistsException:
        # Swallow the exception to support idempotency in the case of
        # duplicated submissions
        pass


def _ecr_client():
    return boto3.client("ecr", endpoint_url=settings.AWS_ECR_ENDPOINT_URL)


def _fargate_new_task_definition(
    role_arn,
    task_family,
    container_name,
    tag,
    task_family_suffix,
    efs_filesystem_id,
    efs_access_point_id,
):
    client = boto3.client("ecs")
    describe_task_response = client.describe_task_definition(taskDefinition=task_family)
    container = [
        container
        for container in describe_task_response["taskDefinition"]["containerDefinitions"]
        if container["name"] == container_name
    ][0]
    container["image"] += (":" + tag) if tag else ""
    describe_task_response["taskDefinition"]["family"] = (
        task_family + ("-" + tag if tag else "") + "-" + task_family_suffix
    )

    if efs_access_point_id:
        volume = next(
            volume
            for volume in describe_task_response["taskDefinition"]["volumes"]
            if volume["name"] == "home_directory"
        )
        del volume["host"]
        volume["efsVolumeConfiguration"] = {
            "fileSystemId": efs_filesystem_id,
            "transitEncryption": "ENABLED",
            "authorizationConfig": {
                "accessPointId": efs_access_point_id,
                "iam": "ENABLED",
            },
        }

    register_tag_response = client.register_task_definition(
        **({"taskRoleArn": role_arn} if role_arn is not None else {}),
        **{
            key: value
            for key, value in describe_task_response["taskDefinition"].items()
            if key
            in [
                "family",
                "executionRoleArn",
                "networkMode",
                "containerDefinitions",
                "volumes",
                "placementConstraints",
                "requiresCompatibilities",
                "cpu",
                "memory",
                "ephemeralStorage",
            ]
        },
    )
    return register_tag_response["taskDefinition"]["taskDefinitionArn"]


def _fargate_task_ip(cluster_name, arn):
    described_task = _fargate_task_describe(cluster_name, arn)

    ip_address_attachements = (
        [
            attachment["value"]
            for attachment in described_task["attachments"][0]["details"]
            if attachment["name"] == "privateIPv4Address"
        ]
        if described_task and "attachments" in described_task and described_task["attachments"]
        else []
    )
    ip_address = ip_address_attachements[0] if ip_address_attachements else ""

    return ip_address


def _fargate_task_describe(cluster_name, arn):
    client = boto3.client("ecs")

    described_tasks = client.describe_tasks(cluster=cluster_name, tasks=[arn])

    task = (
        described_tasks["tasks"][0]
        if "tasks" in described_tasks and described_tasks["tasks"]
        else described_tasks["task"] if "task" in described_tasks else None
    )

    return task


def _fargate_task_stop(cluster_name, task_arn):
    client = boto3.client("ecs")
    sleep_time = 1
    for _ in range(0, 6):
        try:
            client.stop_task(cluster=cluster_name, task=task_arn)
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidParameterException":
                logger.info("Task with arn %s does not exist", task_arn)
                return
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("stop_task failed for %s - Retrying", task_arn)
            gevent.sleep(sleep_time)
            sleep_time = sleep_time * 2
        else:
            return
    raise Exception("Unable to stop Fargate task {}".format(task_arn))


def _fargate_task_run(
    role_arn,
    cluster_name,
    container_name,
    definition_arn,
    security_groups,
    subnets,
    cpu,
    memory,
    command_and_args,
    env,
    s3_sync,
    platform_version,
):
    client = boto3.client("ecs")

    return client.run_task(
        cluster=cluster_name,
        taskDefinition=definition_arn,
        overrides=({"taskRoleArn": role_arn} if role_arn is not None else {})
        | {
            "cpu": cpu,
            "memory": memory,
            "containerOverrides": [
                {
                    **({"command": command_and_args} if command_and_args else {}),
                    "environment": [{"name": name, "value": value} for name, value in env.items()],
                    "name": container_name,
                }
            ]
            + (
                [
                    {
                        "name": "s3sync",
                        "environment": [
                            {"name": name, "value": value} for name, value in env.items()
                        ],
                    }
                ]
                if s3_sync
                else []
            ),
        },
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "assignPublicIp": "DISABLED",
                "securityGroups": security_groups,
                "subnets": subnets,
            }
        },
        platformVersion=platform_version,
    )
