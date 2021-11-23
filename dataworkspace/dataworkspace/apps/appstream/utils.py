import boto3
import gevent

from django.conf import settings


def connect_aws_client(aws_service):
    client = boto3.client(
        aws_service,
        aws_access_key_id=settings.APPSTREAM_AWS_ACCESS_KEY,
        aws_secret_access_key=settings.APPSTREAM_AWS_SECRET_KEY,
        region_name=settings.APPSTREAM_AWS_REGION,
    )
    return client


def get_fleet_status():
    client = connect_aws_client("appstream")

    fleet_status = client.describe_fleets(Names=[settings.APPSTREAM_FLEET_NAME])
    return fleet_status


def get_app_sessions():
    client = connect_aws_client("appstream")

    app_sessions = client.describe_sessions(
        StackName=settings.APPSTREAM_STACK_NAME, FleetName=settings.APPSTREAM_FLEET_NAME
    )

    return app_sessions


def scale_fleet(min_capacity, max_capacity):
    client = connect_aws_client("application-autoscaling")

    scale_response = client.register_scalable_target(
        ServiceNamespace="appstream",
        ResourceId="fleet/" + settings.APPSTREAM_FLEET_NAME,
        ScalableDimension="appstream:fleet:DesiredCapacity",
        MinCapacity=min_capacity,
        MaxCapacity=max_capacity,
    )

    print(scale_response)


def get_fleet_scale():
    client = connect_aws_client("application-autoscaling")

    scale_response = client.describe_scalable_targets(
        ServiceNamespace="appstream",
        ResourceIds=["fleet/" + settings.APPSTREAM_FLEET_NAME],
        ScalableDimension="appstream:fleet:DesiredCapacity",
    )

    return (
        scale_response["ScalableTargets"][0]["MinCapacity"],
        scale_response["ScalableTargets"][0]["MaxCapacity"],
    )


def check_fleet_running():
    fleet_status = get_fleet_status()
    print(fleet_status["Fleets"][0]["State"])

    return fleet_status["Fleets"][0]["State"]


def stop_fleet():
    client = connect_aws_client("appstream")

    stop_response = client.stop_fleet(Name=settings.APPSTREAM_FLEET_NAME)
    print(stop_response)


def start_fleet():
    client = connect_aws_client("appstream")

    start_response = client.start_fleet(Name=settings.APPSTREAM_FLEET_NAME)
    print(start_response)


def restart_fleet():
    print("Stopping fleet")
    stop_fleet()

    while check_fleet_running() != "STOPPED":
        print("Still running")
        gevent.sleep(15)

    print("Fleet stopped")
    print("Starting fleet")
    start_fleet()

    while check_fleet_running() != "RUNNING":
        print("Still starting")
        gevent.sleep(15)

    print("Fleet running")
