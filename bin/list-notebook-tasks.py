# List running notebook tasks sorted by age
# Notes:
#   - Run using aws-vault
#
import csv
import sys
from argparse import ArgumentParser
from datetime import datetime

import boto3
import pytz


def _paginate(records):
    for i in range(0, len(records), 100):
        yield records[i : i + 100]


def main():
    parser = ArgumentParser(
        description="List running tasks on an ECS cluster",
    )
    parser.add_argument("-c", "--cluster", required=True, help="The name of the ECS cluster")
    args = parser.parse_args()
    client = boto3.client("ecs")
    task_arns = []
    next_token = ""
    while True:
        tasks_response = client.list_tasks(
            cluster=args.cluster, desiredStatus="RUNNING", nextToken=next_token
        )
        task_arns.extend(tasks_response["taskArns"])
        next_token = tasks_response.get("nextToken")
        if not next_token:
            break

    task_list = []
    for chunk in _paginate(task_arns):
        for description in client.describe_tasks(cluster=args.cluster, tasks=chunk)["tasks"]:
            if "startedAt" not in description:
                continue
            task_list.append(
                {
                    "started": description["startedAt"],
                    "duration": datetime.now().astimezone(pytz.utc)
                    - description["startedAt"].astimezone(pytz.utc),
                    "arn": description["taskArn"],
                    "task_def": description["taskDefinitionArn"].split("/")[-1].split(":")[0],
                    "task_role": description["overrides"]["taskRoleArn"].split("/")[-1],
                    "email": description["overrides"]["taskRoleArn"]
                    .split("/")[-1]
                    .replace("jhub-", ""),
                    "public_host": description["taskDefinitionArn"]
                    .split("/")[-1]
                    .split(":")[0]
                    .replace("jupyterhub-", ""),
                }
            )

    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=[
            "started",
            "duration",
            "task_role",
            "task_def",
            "public_host",
            "email",
            "arn",
        ],
        quoting=csv.QUOTE_NONNUMERIC,
    )
    writer.writeheader()
    writer.writerows(sorted(task_list, key=lambda x: x["started"]))


if __name__ == "__main__":
    main()
