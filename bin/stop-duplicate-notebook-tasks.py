# Find any duplicate running task definitions on ECS and stop all but the latest
# Notes:
#   - Run using aws-vault
#   - Use --dry-run to run the script without actually stopping the tasks.
#
import sys
from argparse import ArgumentParser
from collections import defaultdict

import boto3


def _paginate(records):
    for i in range(0, len(records), 100):
        yield records[i : i + 100]


def main():
    parser = ArgumentParser(
        description="Find and stop duplicate running tasks on an ECS cluster",
    )
    parser.add_argument("-c", "--cluster", required=True, help="The name of the ECS cluster")
    parser.add_argument(
        "-d", "--dry-run", help="Do not actually delete users", action="store_true"
    )
    args = parser.parse_args()
    client = boto3.client("ecs")

    if args.dry_run:
        print("** This is a dry run. No duplicate tasks will be stopped **")

    print(f"Fetching running tasks in cluster {args.cluster}")

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

    total_running_tasks = len(task_arns)
    print(f"Found {total_running_tasks} running tasks on cluster {args.cluster}")

    print("Finding duplicate task definitions")
    running_tasks = defaultdict(list)
    for chunk in _paginate(task_arns):
        for description in client.describe_tasks(cluster=args.cluster, tasks=chunk)["tasks"]:
            if "startedAt" not in description:
                continue
            running_tasks[description["taskDefinitionArn"].split("/")[-1].split(":")[0]].append(
                {"started": description["startedAt"], "arn": description["taskArn"]}
            )
    total_task_definitions = len(running_tasks)
    print(
        f"Found {total_task_definitions} unique task definitions (out of {total_running_tasks} running tasks)"
    )
    if args.dry_run or (total_running_tasks - total_task_definitions) == 0:
        sys.exit()

    print("Stopping tasks...")
    for task_def_arn, task_details in running_tasks.items():
        if len(task_details) <= 1:
            continue
        tasks_to_stop = sorted(task_details, key=lambda x: x["started"])[:-1]
        print(
            f"Task def {task_def_arn} has {len(task_details)} running tasks. "
            f"Will stop {len(tasks_to_stop)} of them"
        )
        for task in tasks_to_stop:
            client.stop_task(cluster=args.cluster, task=task["arn"])
    print("Done")


if __name__ == "__main__":
    main()
