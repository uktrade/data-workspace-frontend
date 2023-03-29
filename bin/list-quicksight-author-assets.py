# Outputs a comma separated list of all author accounts on quicksight including:
#   1. Username
#   2. email
#   3. Number of analyses
#   4. Number of dashboards
#   5. Number of datasets
#   6. Number of data sources
#
import csv
import sys
from argparse import ArgumentParser
from functools import partial

import boto3


def _fetch_authors(client, account_id):
    next_token = ""
    while True:
        response = client.list_users(
            AwsAccountId=account_id, NextToken=next_token, Namespace="default"
        )
        for user in response["UserList"]:
            if user["Role"] != "AUTHOR":
                continue
            yield {
                "arn": user["Arn"],
                "username": user["UserName"],
                "email": user["Email"],
                "role": user["Role"],
            }
        next_token = response.get("NextToken")
        if not next_token:
            break


def _fetch_assets_for_user(
    client, account_id, user_name, asset_name, response_key, search_field="QUICKSIGHT_OWNER"
):
    assets = []
    next_token = ""
    while True:
        args = {
            "AwsAccountId": account_id,
            "Filters": [{"Operator": "StringEquals", "Name": search_field, "Value": user_name}],
        }
        if next_token:
            args["NextToken"] = next_token

        response = getattr(client, f"search_{asset_name}")(**args)
        for asset in response[response_key]:
            assets.append(
                {
                    "arn": asset["Arn"],
                    "name": asset["Name"],
                }
            )
        next_token = response.get("NextToken")
        if not next_token:
            break
    return assets


def main():
    parser = ArgumentParser(
        description="Output a list of quciksight authors with number of objects associated with the account",
    )
    parser.add_argument("-a", "--account-id", required=True, help="The AWS account ID")
    args = parser.parse_args()
    client = boto3.client("quicksight")
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=[
            "username",
            "email",
            "num_analyses",
            "num_dashboards",
            "num_datasets",
            "num_data_sources",
        ],
        quoting=csv.QUOTE_NONNUMERIC,
    )
    writer.writeheader()
    fetch_assets = partial(_fetch_assets_for_user, client, args.account_id)
    for author in _fetch_authors(client, args.account_id):
        analyses = fetch_assets(author["arn"], "analyses", "AnalysisSummaryList")
        dashboards = fetch_assets(author["arn"], "dashboards", "DashboardSummaryList")
        datasets = fetch_assets(author["arn"], "data_sets", "DataSetSummaries")
        data_sources = fetch_assets(
            author["arn"],
            "data_sources",
            "DataSourceSummaries",
            search_field="DIRECT_QUICKSIGHT_SOLE_OWNER",
        )
        writer.writerow(
            {
                "username": author["username"],
                "email": author["email"],
                "num_analyses": len(analyses),
                "num_dashboards": len(dashboards),
                "num_datasets": len(datasets),
                "num_data_sources": len(data_sources),
            }
        )


if __name__ == "__main__":
    main()
