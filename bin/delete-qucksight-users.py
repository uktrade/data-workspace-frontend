# Given a csv with one column of email address:
#   1. Find the quicksight user id for each user
#   2. Delete the accounts from quicksight
#
# Notes:
#   - Run using aws-vault
#   - Use --dry-run to run the script without actually deleting the users.
#
import csv
from argparse import ArgumentParser

import boto3


def main():
    parser = ArgumentParser(
        description="Given a csv of email addresses, delete the related users from quicksight",
    )
    parser.add_argument(
        "-f", "--file", required=True, help="The path to the csv file containing email addresses"
    )
    parser.add_argument("-a", "--account-id", required=True, help="The AWS account ID")
    parser.add_argument(
        "-d", "--dry-run", help="Do not actually delete users", action="store_true"
    )
    args = parser.parse_args()
    client = boto3.client("quicksight")

    if args.dry_run:
        print("** This is a dry run. No users will be deleted **")

    print(f"Reading emails from csv {args.file}")

    emails = set()
    with open(args.file, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, fieldnames=["email"])
        next(reader)  # skip the header
        for line in reader:
            emails.add(line["email"])

    print(f"Got {len(emails)} emails. Finding matching users on Quicksight")

    email_to_username = {}
    next_token = ""
    while next_token is not None and len(email_to_username) < len(emails):
        response = client.list_users(
            AwsAccountId=args.account_id, NextToken=next_token, Namespace="default"
        )
        for user in response["UserList"]:
            if user["Email"] in emails:
                email_to_username[user["Email"]] = user["UserName"]
                print(f"Found a match for {len(email_to_username)} of {len(emails)} emails")
        next_token = response.get("NextToken")

    print(f"Found {len(email_to_username)} accounts to delete from Quicksight")
    for email, username in email_to_username.items():
        if args.dry_run:
            print(f"Dry run: Would delete user with email {email}")
        else:
            print(f"Deleting user with email {email}")
            client.delete_user(
                AwsAccountId=args.account_id,
                Namespace="default",
                UserName=username,
            )
    print("Fin.")


if __name__ == "__main__":
    main()
